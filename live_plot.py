'''
    Real-time plotting data acquired from 2 DAQ devices (USB-1608fs-Plus) at user-specified time base
    Plots signals from the carotid artery, femoral artery, acoustic and chest strap piezosensors together

'''

from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport
from mcculw import ul
from mcculw.device_info import DaqDeviceInfo
from threading import Thread
from tkinter import *
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import collections, time, sys

try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

# -- For carotid artery, femoral artery, acoustic, and chest strap piezosensor real-time plot
class DAQ:
    def __init__(self, ch, bn, ddi):

        # -- DAQ device properties
        self.use_device_detection = True
        self.dev_id_list = []
        self.board_num = bn
        self.rate = 1000
        self.memhandle = None
        self.ai_info = ddi.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]
        self.channel = ch

        # -- Double-ended queue for storing values that are plotted real-time
        self.data = collections.deque([0] * 100, maxlen=100)

        # -- Time base times
        self.plot_t = 0
        self.previous_t = 0
    
    # -- Read data from analog input channel
    def get_value(self, frame, graph):

        # -- For DAQ devices with a resolution less than or equal to 16
        if self.ai_info.resolution <= 16:

            # -- Read raw value
            raw_value = ul.a_in(self.board_num, self.channel, self.ai_range)

            # -- Convert the raw value to engineering units
            value = ul.to_eng_units(self.board_num, self.ai_range, raw_value)
        
        # -- For DAQ devices with a resolution greater than 16
        else:

            raw_value = ul.a_in_32(self.board_num, self.channel, self.ai_range)
            value= ul.to_eng_units_32(self.board_num, self.ai_range, raw_value)

        # -- Save value to queue 
        self.data.append(value) 

        # -- Update sensor value on matplotlib window
        graph.set_data(range( 100 ), self.data)

    # -- Disconnect DAQ device upon closing the matplotlib window
    def close(self):
        if self.use_device_detection:
            ul.release_daq_device(self.board_num)

# -- List holding 8 instances of DAQ object of 8 analog input channels to read from
daq_instance = [None] * 8

# -- Initial configuration of first USB-1608fs-Plus DAQ device
def inst0():

    # -- Passed board number 0
    config_first_detected_device(0, [])
    daq_dev_info = DaqDeviceInfo(0)

    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')

    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

    # -- Instnaitate DAQ objects for each sensor
    daq_instance[0] = DAQ(0,0, daq_dev_info)

    # -- Wait some time to avoid UL configuration error
    time.sleep(0.1)
    daq_instance[1] = DAQ(1,0, daq_dev_info)

# -- Initial configuration of second USB-1608fs-Plus DAQ device
def inst1():

    # -- Passed board number 1
    config_first_detected_device(1, [])
    daq_dev_info = DaqDeviceInfo(1)

    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')

    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')
    
    # -- Instnaitate DAQ objects for each sensor
    daq_instance[2] = DAQ(0,1, daq_dev_info)

    # -- Wait some time to avoid UL configuration error
    time.sleep(0.1)
    daq_instance[3] = DAQ(1,1, daq_dev_info)
    time.sleep(0.1)
    daq_instance[4] = DAQ(2,1, daq_dev_info)
    time.sleep(0.1)
    daq_instance[5] = DAQ(3,1, daq_dev_info)
    time.sleep(0.1)
    daq_instance[6] = DAQ(4,1, daq_dev_info)
    time.sleep(0.1)
    daq_instance[7] = DAQ(5,1, daq_dev_info)

def plot_piezos(tb):
# -- If program log is included    
# def plot_piezos(tb, log):
    
    # -- Concurrent configuration of the two DAQ devices
    for_board0 = Thread(target=inst0)
    for_board1 = Thread(target=inst1)

    for_board0.start()
    for_board1.start()

    for_board0.join()
    for_board1.join()

    # -- Assignment of each DAQ object to corresponding channel/sensor

    board_zero_ch_zero = daq_instance[0]    # Carotid artery piezosensor
    board_zero_ch_one = daq_instance[1]     # Femoral artery piezosensor  
    board_one_ch_zero = daq_instance[2]     # Acoustic piezosensor
    board_one_ch_one = daq_instance[3]      # Chest strap piezosensors
    board_one_ch_two = daq_instance[4]      
    board_one_ch_three = daq_instance[5]    
    board_one_ch_four = daq_instance[6]     
    board_one_ch_five = daq_instance[7]     

    # -- Period at which plot animations update in milliseconds
    time_base = tb

    # -- matplotlib graph properties
    fig, ((ax0, ax1),(ax2, ax3),(ax4, ax5), (ax6, ax7)) = plt.subplots(nrows=4, ncols=2, sharex=True, sharey='row', figsize=(20,8))

    ax0.set_xlim([0, 100])
    ax0.set_ylim([-3,3])

    ax1.set_xlim([0, 100])

    ax2.set_xlim([0, 100])
    ax2.set_ylim([0,10]) 

    ax3.set_xlim([0, 100])

    ax4.set_xlim([0, 100])
    ax4.set_ylim([0,10]) 

    ax5.set_xlim([0, 100])

    ax6.set_xlim([0, 100])
    ax6.set_ylim([0,10])  
    
    ax7.set_xlim([0, 100])

    carotid_label = 'Carotid Piezo'
    carotid_graph = ax0.plot([], [], label=carotid_label, linewidth=0.5)[0]

    femoral_label = 'Femoral Piezo'
    femoral_graph = ax1.plot([], [], label=femoral_label, linewidth=0.5)[0]

    acoustic_label = 'Piezo CH0'
    acoustic_graph = ax2.plot([], [], label=acoustic_label, linewidth=0.5)[0]

    ch1_label = 'Piezo CH1'
    ch1_graph = ax3.plot([], [], label=ch1_label, linewidth=0.5)[0]

    ch2_label = 'Piezo CH2'
    ch2_graph = ax4.plot([], [], label=ch2_label, linewidth=0.5)[0]

    ch3_label = 'Piezo CH3'
    ch3_graph = ax5.plot([], [], label=ch3_label, linewidth=0.5)[0]
    
    ch4_label = 'Piezo CH4'
    ch4_graph = ax6.plot([], [], label=ch4_label, linewidth=0.5)[0]

    ch5_label = 'Piezo CH5'
    ch5_graph = ax7.plot([], [], label=ch5_label, linewidth=0.5)[0]

    # -- Callback functions to read data from analog inputs and update the frame of the live plots   
    carotid_anim = animation.FuncAnimation(fig, board_zero_ch_zero.get_value, fargs=(carotid_graph,), interval=time_base)  
    femoral_anim = animation.FuncAnimation(fig, board_zero_ch_one.get_value, fargs=(femoral_graph,), interval=time_base)  
    acoustic_anim = animation.FuncAnimation(fig, board_one_ch_zero.get_value, fargs=(acoustic_graph,), interval=time_base)    
    ch1_anim = animation.FuncAnimation(fig, board_one_ch_one.get_value, fargs=(ch1_graph,), interval=time_base)  
    ch2_anim = animation.FuncAnimation(fig, board_one_ch_two.get_value, fargs=(ch2_graph,), interval=time_base)  
    ch3_anim = animation.FuncAnimation(fig, board_one_ch_three.get_value, fargs=(ch3_graph,), interval=time_base)
    ch4_anim = animation.FuncAnimation(fig, board_one_ch_four.get_value, fargs=(ch4_graph,), interval=time_base) 
    ch5_anim = animation.FuncAnimation(fig, board_one_ch_five.get_value, fargs=(ch5_graph,), interval=time_base) 

    # -- matplotlib graph properties
    fig.tight_layout()
    
    axes = [ax0, ax1, ax2, ax3, ax4, ax5, ax6, ax7]
    for ax in axes:
        ax.legend(loc="upper left")

    mng = plt.get_current_fig_manager()
    mng.window.showMaximized()
    plt.show()

    # -- Disconnect
    try:
        board_zero_ch_zero.close()
        board_zero_ch_one.close()
        board_one_ch_zero.close()
        board_one_ch_one.close()
        board_one_ch_two.close()
        board_one_ch_three.close()
        board_one_ch_four.close()
        board_one_ch_five.close()

        del board_zero_ch_zero, board_zero_ch_one, board_one_ch_zero, board_one_ch_one, board_one_ch_two, board_one_ch_three, board_one_ch_four, board_one_ch_five
        
        # -- If program log is included
        # Label(log, text='Successful Disconnection.', anchor='w').grid(pady=(0,5))

        print('  Successfully disconnected.\n\n')

    except:

        # -- If program log is included
        # Label(log, text='ERROR: DISCONNECTION FAILURE',anchor='w').grid()

        print('  ERROR: DISCONNECTION FAILURE\n')
        sys.exit()
