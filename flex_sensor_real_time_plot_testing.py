'''
    Simultaneous real-time plotting and data acquisition of the Bend Labs digital one-axis flex sensor.
    Measures angular displacement (bend) in degrees, from the resting position of the sensor.
    Optional time base selection and saving format manipulation of the spreadsheet that stores acquired data.
    Using I2C protocol to communicate data between the sensor and Arduino Due.
    Data received and read by Windows PC via serial port connection.
    No timer implementation to start the program at a specified time and end the program after a specified duration.

    Hardware Setup at the Time of Program Development:
     - Bend Labs digital one-axis flex sensor connected to a custom PCB using a 6-pin male header
     - Custom PCB interfaces with the sensor without any signal processing (carries signals)
     - Jumper wires on custom PCB connects SDA, SCL, nRST, and nDRDY lines to pins SDA20, SCL21, 3, and 4 on the Arduino Due respectively
     - Using programming serial port on the Arduino Due to connect to a Windows PC with a micro-USB-B to USB-A cable

    Software Setup at the Time of Program Development:
    - Uploaded bend_polled_demo.ino to the Arduino Due using Arduino IDE v1.8.15 for flex sensor configuration prior to scanning 
      (see bend_polled_demo folder in the repository for the uploaded code and dependencies)

    - Installed Software:
        Python 3.9.2
        pip 21.1.3
        matplotlib 3.4.2
        pandas 1.2.4
        pyserial 3.5

'''

from threading import Thread
import serial, time, collections, sys
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd

# -- Handles real-time plotting and data acquisition
class RealTimePlot:
    def __init__(self, port_name='COM3', baud_rate=115200, plot_limit=100, bytes_per_data_point = 8):
        self.port = port_name
        self.baud = baud_rate
        self.max_limit = plot_limit
        self.bytes_per_data_point = bytes_per_data_point

        # -- Double-ended queue for storing values that are plotted real-time
        self.data = collections.deque([0] * plot_limit, maxlen=plot_limit)

        # -- Stores all acquired values to export to a spreadsheet
        self.spreadsheet_data = []

        # -- Program status indicators
        self.is_running = True
        self.is_receiving = False
        self.background_thread = None

        # -- Time base times
        self.graph_t = 0
        self.previous_t = 0

        # -- Establish a serial port connection
        print('Trying to connect to: ' + str(port_name) + ' at ' + str(baud_rate) + ' BAUD.')
        try:
            self.serial_connection = serial.Serial(port_name, baud_rate, timeout=4)
            print('Connected to ' + str(port_name) + ' at ' + str(baud_rate) + ' BAUD.')
        except:
            print("Failed to connect with " + str(port_name) + ' at ' + str(baud_rate) + ' BAUD.')
            sys.exit()

        self.pre_scan()

    # -- Read from the serial port until the invalid data point containing the successful connection notice is removed
    def pre_scan(self):

        initial_scan = ''

        # -- Successful connection notice
        while initial_scan != "One Axis ADS initialization succeeded...":
            initial_scan = self.serial_connection.readline()
            try:
                initial_scan = initial_scan.decode("utf-8")
                initial_scan = initial_scan[:-2]
            except UnicodeDecodeError:
                pass

    # -- Set up background thread to read data
    def readline_data(self):

        if self.background_thread == None:
            self.background_thread = Thread(target=self.background_daq)
            self.background_thread.start()

            # -- Prevent plotting until background thread begins reading from the serial port
            while self.is_receiving != True:
                time.sleep(0.1)

    def update_and_save(self, frame, graph, graph_data_label, graph_label, time_base_label):

        # -- Update plot interval (time base) on matplotlib window
        current_t = time.perf_counter()
        self.graph_t = int((current_t - self.previous_t) * 1000) 
        self.previous_t = current_t
        time_base_label.set_text('Plot Interval = ' + str(self.graph_t) + 'ms')

        # -- Decode value read from background thread and save to queue 
        value = float((self.raw_data).decode()[:-2]) 
        self.data.append(value)   

        # -- Update sensor value on matplotlib window
        graph.set_data(range(self.max_limit), self.data)
        graph_data_label.set_text('[' + graph_label + '] = ' + str(value))
       
        self.spreadsheet_data.append(self.data[-1])

    # -- Read data from the serial port
    def background_daq(self):  

        # -- Time for buffer to acquire data
        time.sleep(1.0)  
        self.serial_connection.reset_input_buffer()

        # -- Read data until program is terminated
        while self.is_running:
            self.raw_data = self.serial_connection.readline()
            self.is_receiving = True
    
    # -- Closes serial port connection upon closing the matplotlib window
    def close(self):

        # -- Update status of program
        self.is_running = False

        # -- Complete the background thread
        self.background_thread.join()

        # -- Close serial port connection
        self.serial_connection.close()
        print('Successfully disconnected.')

        # Format data in any preferred way here
        df = pd.DataFrame(self.spreadsheet_data)

        # -- Export to CSV file 
        df.to_csv('flex_sensor_data_test_recording.csv')

# -- Preparing the real-time plot
def scan():

    # -- Serial port properties
    port_name = 'COM3'
    baud_rate = 115200
    plot_limit = 100
    bytes_per_data_point = 8        

    # -- Instantiates object with serial port connection properties
    serial_obj = RealTimePlot(port_name, baud_rate, plot_limit, bytes_per_data_point)  

    # -- Start background thread for receiving data
    serial_obj.readline_data()                                               

    # -- Period at which plot animation updates in milliseconds
    time_base = 50 

    # -- matplotlib graph properties
    fig = plt.figure()
    ax = plt.axes( xlim=( 0, plot_limit ), ylim=( -100, 100 ) )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Angular Displacement (deg)")

    # -- Graph text animation properties
    graph_label = 'Flex Sensor'
    time_base_label = ax.text(0.50, 0.95, '', transform=ax.transAxes)
    graph = ax.plot([], [], label=graph_label, linewidth=0.5)[0]
    graph_data_label = ax.text(0.50, 0.90, '', transform=ax.transAxes)

    # -- Callback function to read data from the serial port and update the frame of the live plot
    anim = animation.FuncAnimation(fig, serial_obj.update_and_save, fargs=(graph, graph_data_label, graph_label, time_base_label), interval=time_base)    # fargs has to be a tuple

    plt.legend(loc="upper left")
    plt.show()

    # -- Close serial port connection
    serial_obj.close()

if __name__ == '__main__':
    
    # -- Begin scan
    scan()
    