'''
    Real-time plotting data acquired from a USB-1608fs-Plus DAQ device and the serial port at user-specified time base
    Plots signals from the ECG and flex sensor together

'''

from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport
from mcculw import ul
from mcculw.device_info import DaqDeviceInfo
from tkinter import *
from threading import Thread
import matplotlib.animation as animation
import collections, time, serial, sys
import matplotlib.pyplot as plt

try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

# -- For ECG electrode real-time plot
class DAQ:
    def __init__(self, ch, bn):

        # -- DAQ device properties
        self.use_device_detection = True
        self.dev_id_list = []
        self.board_num = bn
        self.rate = 1000
        self.memhandle = None

        # -- Double-ended queue for storing values that are plotted real-time
        self.data = collections.deque([0] * 100, maxlen=100)

        # -- Time base times
        self.ecg_graph_t = 0
        self.ecg_previous_t = 0

        # -- Configure DAQ device with ECG connected to it
        if self.use_device_detection:
            config_first_detected_device(self.board_num, self.dev_id_list)

        daq_dev_info = DaqDeviceInfo(self.board_num)

        if not daq_dev_info.supports_analog_input:
            raise Exception('Error: The DAQ device does not support analog input')

        print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

        # -- DAQ device properties
        self.ai_info = daq_dev_info.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]
        self.channel = ch

    # -- Read data from analog input channel
    def get_value(self, frame, ecg_graph, ecg_graph_data_label, ecg_graph_label, ecg_tb_label):

        # -- For DAQ devices with a resolution less than or equal to 16
        if self.ai_info.resolution <= 16:

            # -- Read raw value
            raw_value = ul.a_in(board_num=self.board_num, channel=self.channel, ul_range=self.ai_range)
            
            # -- Convert the raw value to engineering units
            value = ul.to_eng_units(self.board_num, self.ai_range, raw_value)

        # -- For DAQ devices with a resolution greater than 16
        else:

            raw_value = ul.a_in_32(self.board_num, self.channel, self.ai_range)
            value= ul.to_eng_units_32(self.board_num, self.ai_range, raw_value)

        # -- Update plot interval (time base) on matplotlib window
        ecg_current_t = time.perf_counter()
        self.ecg_graph_t = int((ecg_current_t - self.ecg_previous_t) * 1000)     # the first reading will be erroneous
        self.ecg_previous_t = ecg_current_t
        ecg_tb_label.set_text('Plot Interval = ' + str(self.ecg_graph_t) + 'ms')  

        # -- Save value to queue 
        self.data.append(value)    

        # -- Update sensor value on matplotlib window
        ecg_graph.set_data(range( 100 ), self.data)
        ecg_graph_data_label.set_text('[' + ecg_graph_label + '] = ' + str(value))

    # -- Disconnect DAQ device upon closing the matplotlib window
    def close(self):
        if self.use_device_detection:
            ul.release_daq_device(self.board_num)

# -- For flex sensor real-time plot
class SerialPort:
    def __init__(self, port_name = 'COM3', baud_rate = 115200, plot_limit = 100, bytes_per_data_point = 8):
        self.port = port_name
        self.baud = baud_rate
        self.max_limit = plot_limit
        self.bytes_per_data_point = bytes_per_data_point

        # -- Double-ended queue for storing values that are plotted real-time
        self.data = collections.deque([0] * plot_limit, maxlen=plot_limit)

        # -- Real-time plot status indicators
        self.is_running = True
        self.is_receiving = False
        self.background_thread = None

        # -- Time base times
        self.flex_graph_t = 0
        self.flex_previous_t = 0

        # -- Establish serial port connection
        try:
            self.serial_connection = serial.Serial(port_name, baud_rate, timeout=4)
            print('  Connected to ' + str(port_name) + ' at ' + str(baud_rate) + ' BAUD.\n')
        except:
            print("  ERROR: FAILED TO CONNECT WITH " + str(port_name) + ' AT ' + str(baud_rate) + ' BAUD.\n')

        self.pre_plot()
    
    # -- Readline until successful connection indicator is removed
    def pre_plot(self):

        initial_scan = ''

        while initial_scan != "One Axis ADS initialization succeeded...":
            initial_scan = self.serial_connection.readline()
            try:
                initial_scan = initial_scan.decode("utf-8")
                initial_scan = initial_scan[:-2]
            except UnicodeDecodeError:
                pass

    # -- Set up background thread to read flex sensor data
    def readline_data(self):

        if self.background_thread == None:
            self.background_thread = Thread(target=self.background_read)
            self.background_thread.start()

            # -- Prevent plotting until background thread begins reading from the serial port
            while self.is_receiving != True:
                time.sleep(0.1)

    def update_value(self, frame, flex_graph, flex_graph_data_label, flex_graph_label, flex_tb_label):
        
        # -- Update plot interval (time base) on matplotlib window
        flex_current_t = time.perf_counter()
        self.flex_graph_t = int((flex_current_t - self.flex_previous_t) * 1000)     # the first reading will be erroneous
        self.flex_previous_t = flex_current_t
        flex_tb_label.set_text('Plot Interval = ' + str(self.flex_graph_t) + 'ms')

        # -- Decode value read from background thread and save to queue
        value = float((self.rawData).decode()[:-2]) 
        self.data.append(value)    

        # -- Update sensor value on matplotlib window
        flex_graph.set_data(range(self.max_limit), self.data)
        flex_graph_data_label.set_text('[' + flex_graph_label + '] = ' + str(value))

    # -- Read flex sensor data from the serial port
    def background_read(self):    

        # -- Time for buffer to acquire data
        time.sleep(1.0)
        self.serial_connection.reset_input_buffer()

        # -- Read data until real-time plotting is terminated
        while self.is_running:
            self.rawData = self.serial_connection.readline()
            self.is_receiving = True

    # -- Closes serial port connection upon closing the matplotlib window
    def close(self):

        # -- Update status of plot
        self.is_running = False

        self.background_thread.join()
        self.serial_connection.close()

def plot_flexode(tb):
# -- If program log is included
# def plot_flexode( tb, log ):

    # -- Instantiate DAQ device object with board properties to connect to the ECG electrode analog channel
    d = DAQ(6,1)

    # -- Instantiate serial port obejct with port properties to connect to the flex sensor
    s = SerialPort('COM3', 115200, 100, 8) 

    # -- Period at which plot animations update in milliseconds
    time_base = tb   

    # -- matplotlib graph properties
    fig, (ax0, ax1) = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(20,6))

    ax0.set_xlim([0, 100])
    ax0.set_ylim([-2,6])
    ax0.set_ylabel("Amplitude (V)") 

    ax1.set_xlim([0, 100])
    ax1.set_ylim([-100,100]) 
    ax1.set_ylabel("Angular Displacement (deg)")

    # -- ECG electrode graph text animation properties
    ecg_graph_label = 'ECG Electrode'
    ecg_tb_label = ax0.text(0.50, 0.95, '', transform=ax0.transAxes)
    ecg_graph = ax0.plot([], [], label=ecg_graph_label, linewidth=0.5)[0]
    ecg_graph_data_label = ax0.text(0.50, 0.90, '', transform=ax0.transAxes)

    # -- Flex sensor graph text animation properties
    flex_graph_label = 'Flex Sensor'
    flex_tb_label = ax1.text(0.50, 0.95, '', transform=ax1.transAxes)
    flex_graph = ax1.plot([], [], label=flex_graph_label, linewidth=0.5)[0]
    flex_graph_data_label = ax1.text(0.50, 0.90, '', transform=ax1.transAxes)

    # -- Starts background thread for receiving flex sensor data
    s.readline_data()

    # -- Callback functions to read data from inputs and update the frame of the live plots   
    ecg_anim = animation.FuncAnimation( fig, d.get_value, fargs=( ecg_graph, ecg_graph_data_label, ecg_graph_label, ecg_tb_label ), interval=time_base )    
    flex_anim = animation.FuncAnimation( fig, s.update_value, fargs=( flex_graph, flex_graph_data_label, flex_graph_label, flex_tb_label ), interval=time_base )
    
    # -- matplotlib graph properties
    fig.tight_layout()
    ax0.legend(loc="upper left")
    ax1.legend(loc="upper left")

    mng = plt.get_current_fig_manager()
    mng.window.showMaximized()
    plt.show()

    # -- Close connection to DAQ device and serial port
    try:
        s.close()
        d.close()

        del s, d
        
        # -- If program log is included
        # Label(log, text='Successful Disconnection.', anchor='w').grid(pady=(0,5))

        print('  Successfully disconnected.\n\n')
    except:

        # -- If program log is included
        # Label(log, text='ERROR: DISCONNECTION FAILURE', anchor='w').grid()

        print('  ERROR: DISCONNECTION FAILURE\n')
        sys.exit()