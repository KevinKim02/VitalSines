'''
    Must have acosutic chest strap board connected to InstalCAL as board 0 and nothing else
'''
from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport

from ctypes import c_double, cast, POINTER, addressof, sizeof
from time import sleep

from mcculw import ul
from mcculw.enums import ScanOptions, FunctionType, Status
from mcculw.device_info import DaqDeviceInfo

from threading import Thread
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import CheckButtons
import time, serial, os, sys


try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

# By default, the example detects and displays all available devices and
# selects the first device listed. Use the dev_id_list variable to filter
# detected devices by device ID (see UL documentation for device IDs).
# If use_device_detection is set to False, the board_num variable needs to
# match the desired board number configured with Instacal.
global save_complete
save_complete = False

global terminate
terminate = False

use_device_detection = True
dev_id_list = []
board_num = 0
print()
full_name = input('Enter the patient\'s full name: ')
print()
sex = input('Enter the sex (M/F): ')
print()
rate = int(input('Enter the rate (scans/s): '))
memhandle = None
# The size of the UL buffer to create, in seconds
print()
buffer_size_seconds = int(input( 'Enter the recording duration: ' ))
# The number of buffers to write. After this number of UL buffers are
# written to file, the example will be stopped.
num_buffers_to_write = 1

if use_device_detection:
    config_first_detected_device(board_num, dev_id_list)
daq_dev_info = DaqDeviceInfo(board_num)
if not daq_dev_info.supports_analog_input:
    raise Exception('Error: The DAQ device does not support '
                    'analog input')
print('\nActive DAQ device: ', daq_dev_info.product_name, ' (',
      daq_dev_info.unique_id, ')\n', sep='')
ai_info = daq_dev_info.get_ai_info()
low_chan = 0
high_chan = 6
num_chans = high_chan - low_chan + 1
# Create a circular buffer that can hold buffer_size_seconds worth of
# data, or at least 10 points (this may need to be adjusted to prevent
# a buffer overrun)
points_per_channel = max(rate * buffer_size_seconds + 1, 10)
# Some hardware requires that the total_count is an integer multiple
# of the packet size. For this case, calculate a points_per_channel
# that is equal to or just above the points_per_channel selected
# which matches that requirement.
if ai_info.packet_size != 1:
    packet_size = ai_info.packet_size
    remainder = points_per_channel % packet_size
    if remainder != 0:
        points_per_channel += packet_size - remainder
ul_buffer_count = points_per_channel * num_chans
# Write the UL buffer to the file num_buffers_to_write times.
points_to_write = ul_buffer_count * num_buffers_to_write
# When handling the buffer, we will read 1/10 of the buffer at a time
write_chunk_size = int(ul_buffer_count / points_per_channel)

ai_range = 1 #ai_info.supported_ranges[0]

scan_options = (ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS |
                ScanOptions.SCALEDATA)
memhandle = ul.scaled_win_buf_alloc(ul_buffer_count)
# Allocate an array of doubles temporary storage of the data
write_chunk_array = (c_double * write_chunk_size)()
# Check if the buffer was successfully allocated
if not memhandle:
    raise Exception('Failed to allocate memory')

ser = serial.Serial('COM3', 115200, timeout=1)
ser.flushInput()
digital_data = []
discrete_data = []
timestamp = []
flex_timestamp = []
elapsed = 0
scan = ""
sampling_rate = 1
if (rate < 100):
    sampling_rate = 0

delay = 1 / rate

while scan != "One Axis ADS initialization succeeded...":
    scan = ser.readline()
    try:
        scan = scan.decode("utf-8")
        scan = scan[:-2]
    except UnicodeDecodeError:
        pass

path = os.getcwd() + '/'
file_name = datetime.now().strftime('%Y-%m-%d %H;%M') + ' -- ' + full_name + ' (' + sex + ') -- ' + str(rate) + 'Hz for ' + str(buffer_size_seconds) + 's .csv' 
file_name_exc = datetime.now().strftime('%Y-%m-%d %H;%M') + ' -- ' + full_name + ' (' + sex + ') -- ' + str(rate) + 'Hz for ' + str(buffer_size_seconds) + 's -- ' 

def piezodes():
    print( 'Scanning . . .', end =" ")
    # Start the scan
    t0 = time.time()
    ul.a_in_scan(
        board_num, low_chan, high_chan, ul_buffer_count,
        rate, ai_range, memhandle, scan_options)

    status = Status.IDLE
    # Wait for the scan to start fully
    while status == Status.IDLE:
        status, _, _ = ul.get_status(board_num, FunctionType.AIFUNCTION)
    # Create a file for storing the data
    with open(file_name, 'w') as f:
        # Write a header to the file
    
        f.write('Time (s)' + ',')
        f.write(' ' + ',')
        for chan_num in range(low_chan, high_chan):
            f.write('Piezo Channel ' + str(chan_num) + ' (V)'+ ',')
        f.write('Electrode (V)' + ',')    
        f.write(u'\n')
        # Start the write loop
        prev_count = 0
        prev_index = 0
        write_ch_num = low_chan
        t=0
        print ('------------start:  ' + str(time.time()))
        while status != Status.IDLE:
            # Get the latest counts
            status, curr_count, _ = ul.get_status(board_num,
                                                  FunctionType.AIFUNCTION)
            new_data_count = curr_count - prev_count
            # Check for a buffer overrun before copying the data, so
            # that no attempts are made to copy more than a full buffer
            # of data
            if new_data_count > ul_buffer_count:
                # Print an error and stop writing
                ul.stop_background(board_num, FunctionType.AIFUNCTION)
                print('A buffer overrun occurred')
                break
            # Check if a chunk is available
            if new_data_count > write_chunk_size:
                wrote_chunk = True
                # Copy the current data to a new array
                # Check if the data wraps around the end of the UL
                # buffer. Multiple copy operations will be required.
                if prev_index + write_chunk_size > ul_buffer_count - 1:
                    first_chunk_size = ul_buffer_count - prev_index
                    second_chunk_size = (
                        write_chunk_size - first_chunk_size)
                    # Copy the first chunk of data to the
                    # write_chunk_array
                    ul.scaled_win_buf_to_array(
                        memhandle, write_chunk_array, prev_index,
                        first_chunk_size)
                    # Create a pointer to the location in
                    # write_chunk_array where we want to copy the
                    # remaining data
                    second_chunk_pointer = cast(addressof(write_chunk_array)
                                                + first_chunk_size
                                                * sizeof(c_double),
                                                POINTER(c_double))
                    # Copy the second chunk of data to the
                    # write_chunk_array
                    ul.scaled_win_buf_to_array(
                        memhandle, second_chunk_pointer,
                        0, second_chunk_size)
                else:
                    # Copy the data to the write_chunk_array
                    ul.scaled_win_buf_to_array(
                        memhandle, write_chunk_array, prev_index,
                        write_chunk_size)
                # Check for a buffer overrun just after copying the data
                # from the UL buffer. This will ensure that the data was
                # not overwritten in the UL buffer before the copy was
                # completed. This should be done before writing to the
                # file, so that corrupt data does not end up in it.
                status, curr_count, _ = ul.get_status(
                    board_num, FunctionType.AIFUNCTION)
                if curr_count - prev_count > ul_buffer_count:
                    # Print an error and stop writing
                    ul.stop_background(board_num, FunctionType.AIFUNCTION)
                    print('A buffer overrun occurred')
                    break
                f.write(str(t) + ',')
                f.write(' ' + ',' )
                t+=delay
                for i in range(write_chunk_size):
                    f.write(str(write_chunk_array[i]) + ',')
                    write_ch_num += 1
                    if write_ch_num == high_chan + 1:
                        write_ch_num = low_chan
                        f.write(u'\n')
            else:
                wrote_chunk = False
            if wrote_chunk:
                # Increment prev_count by the chunk size
                prev_count += write_chunk_size
                # Increment prev_index by the chunk size
                prev_index += write_chunk_size
                # Wrap prev_index to the size of the UL buffer
                prev_index %= ul_buffer_count
                if prev_count >= points_to_write:
                    break
            else:
                # Wait a short amount of time for more data to be
                # acquired.
                sleep(0.1)
        print ('------------end:  ' + str(time.time()))
    #print("Done in " + '{:.1f}'.format(time.time() - t0) + ' seconds.', end =" ")
    #print()
    ul.stop_background(board_num, FunctionType.AIFUNCTION)
    if memhandle:
        # Free the buffer in a finally block to prevent  a memory leak.
        ul.win_buf_free(memhandle)
    if use_device_detection:
        ul.release_daq_device(board_num)


def flex_sensor():
    if sampling_rate == 0:
        ti = time.time()
        digital_data.append(ser.readline())
        while time.time() - ti <= buffer_size_seconds: 
            digital_data.append(ser.readline())
            sleep( delay )
    else:
        ti = time.time()
        digital_data.append(ser.readline())
        while time.time() - ti <= buffer_size_seconds: 
            digital_data.append(ser.readline())
    ser.close()

    if( sampling_rate ==0 and len(digital_data) != rate + 1 ):
        print('Flex Sensor Data Acquisition Failed. Please run the scan again.') 
        global terminate 
        terminate = True
        print()
        sys.exit()

    for i in range(len(digital_data)):
        temp = digital_data[i].decode("utf-8")
        digital_data[i] = temp[:-2]    

    increment = 0
    while increment <= buffer_size_seconds:
        timestamp.append( increment )
        increment = float('{:.5f}'.format(increment + delay)) 

    increment = 0
    while increment <= buffer_size_seconds:
        flex_timestamp.append( increment )
        increment = float('{:.5f}'.format(increment + 0.01)) 

    sleep( 1 )
    fdf = pd.read_csv(path+file_name)
    end_save = False
    while end_save == False:
        print()
        global save_options
        save_options = input( "Save Data to One File (0) - Save Data to Separate Files (1) --- " )
    
        if save_options == '0':
            if sampling_rate == 0:
                fdf.insert(1, "Angular Displacement (Degrees)", digital_data)
            else:
                index = 0
                for i in range( len(timestamp)):
                    if (float('{:.5f}'.format(timestamp[i]*100))).is_integer():
                        discrete_data.append(digital_data[index])
                        index += 1
                    else:
                        discrete_data.append(' ')
                fdf.insert(1, "Angular Displacement (Degrees)", discrete_data)
            fdf.drop('Unnamed: 9', inplace=True, axis=1)
            fdf.to_csv(file_name, index=False)
            end_save = True

        elif save_options == '1':
            # Flex Sensor
            if sampling_rate == 0:
                flex_time = fdf.loc[:,['Time (s)']]
            else: 
                flex_time = flex_timestamp
            ddf = pd.DataFrame([flex_time, digital_data])
            ddf.to_csv(file_name_exc + 'Flex Sensor .csv', index=False)

            # Split piezo and electrode
            electrode_data = fdf.loc[:,['Time (s)', 'Electrode (V)']]
            fdf.drop('Electrode (V)', inplace=True, axis=1)
            fdf.drop('Unnamed: 9', inplace=True, axis=1)
            fdf.to_csv(file_name, index=False)
            os.rename(path + file_name, file_name_exc + 'Piezosensors .csv')

            edf = pd.DataFrame(electrode_data)
            edf.to_csv(file_name_exc + 'Electrodes .csv', index=False)
            end_save = True
        
        else:
            print()
            print('Please enter a valid entry.')
    global save_complete
    save_complete = True

if __name__ == '__main__':
    Thread(target = piezodes).start()
    Thread(target = flex_sensor).start()
    sleep(buffer_size_seconds + 0.5)
    if terminate:
        sys.exit()
    while save_complete == False:
        sleep(1)
    end = False

    if save_options == '0':
        df = pd.read_csv(file_name)
    else:
        df = pd.read_csv(file_name_exc + 'Piezosensors .csv')
        ef = pd.read_csv(file_name_exc + 'Electrodes .csv')
    while end == False:
        print()
        options = input( "Open Spreadsheet (0) - Plot Piezosensor Data (1) - Plot Electrode Data (2) - Plot Flex Sensor Data (3) - Exit (4) --- " )
        if options != '0' and (int(options) < 4 and int(options) > -1):
            plt.style.use('fivethirtyeight')
            plot_window = plt.get_current_fig_manager()
            plot_window.window.showMaximized()
            plt.axes()
            plt.xlim([0,buffer_size_seconds])
        if options == '0':
            if save_options == '0':
                os.startfile(file_name)
            else:
                open_end = False
                while open_end == False:
                    print()
                    open_options = input( "->  Open Piezosensor Data (0) - Open Electrode Data (1) - Open Flex Sensor Data (2) - Back (3) --- " )
                    if open_options == '0':
                        os.startfile(file_name_exc + 'Piezosensors .csv')
                        sleep(0.6)
                    elif open_options == '1':
                        os.startfile(file_name_exc + 'Electrodes .csv')
                        sleep(0.6)
                    elif open_options == '2':
                        os.startfile(file_name_exc + 'Flex Sensor .csv')
                        sleep(0.6)
                    elif open_options == '3':
                        break
                    else:
                        print()
                        print('Please enter a valid entry.')

        elif options == '1':
            ch0, = plt.plot(df['Time (s)'], df['Piezo Channel 0 (V)'], label='CH0', linewidth=0.5, color='r')
            ch1, = plt.plot(df['Time (s)'], df['Piezo Channel 1 (V)'], label='CH1', linewidth=0.5, color='y')
            ch2, = plt.plot(df['Time (s)'], df['Piezo Channel 2 (V)'], label='CH2', linewidth=0.5, color='g')
            ch3, = plt.plot(df['Time (s)'], df['Piezo Channel 3 (V)'], label='CH3', linewidth=0.5, color='b')
            ch4, = plt.plot(df['Time (s)'], df['Piezo Channel 4 (V)'], label='CH4', linewidth=0.5, color='c')
            ch5, = plt.plot(df['Time (s)'], df['Piezo Channel 5 (V)'], label='CH5', linewidth=0.5, color='m')
            channel = [ch0, ch1, ch2, ch3, ch4, ch5]
            plt.title('Piezosensor Output (Channel 0-5)', loc='center', pad=16 )
            plt.xlabel('Time (s)')
            plt.ylabel('Amplitude (V)')
            plt.subplots_adjust(left=0.1, bottom=0.1, right=0.95, top=0.95)
            plt.ylim([0, 10])
            label = ['CH0','CH1','CH2','CH3','CH4','CH5']
            label_on = [True, True, True, True, True, True]

            button_space = plt.axes([0.92, 0.4, 0.15, 0.15])
            button = CheckButtons(button_space, label, label_on)
            
            def set_visible(labels):
                i = label.index(labels)
                channel[i].set_visible(not channel[i].get_visible())
                plt.draw()

            [rec.set_facecolor(channel[i].get_color()) for i, rec in enumerate(button.rectangles)]
            
            button.on_clicked(set_visible)
            plt.show()
        elif options == '2':
            if save_options == '0':
                plt.plot(df['Time (s)'], df['Electrode (V)'], linewidth=0.6, color='r') 
            else:
                plt.plot(ef['Time (s)'], ef['Electrode (V)'], linewidth=0.6, color='r') 
            
            plt.title('Electrode Output', loc='center', pad=16)
            plt.xlabel('Time (s)')
            plt.ylabel('Amplitude (V)')
            plt.show()
        elif options == '3':
            if sampling_rate == 0:
                plt.plot(df['Time (s)'], df['Angular Displacement (Degrees)'], linewidth=0.6, color='r')
            else:
                plt.plot(flex_timestamp, digital_data, linewidth=0.6, color='r')
            plt.title('Flex Sensor Output', loc='center', pad=16)
            plt.xlabel('Time (s)')
            plt.ylabel('Angular Displacement (Degrees)')
            plt.show()
        elif options == '4':
            end = True
        else:
            print()
            print('Please enter a valid entry.')
    print()
    print( 'Complete.')

