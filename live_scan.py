'''
    Simultaneous data acquisition from 2 DAQ devices (USB-1608fs-Plus) and the serial port for user-specified duration at user-specified sampling rate
    Saves all data into one or multiple spreadsheets depeding on user-entry

'''

from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport
from ctypes import c_double, cast, POINTER, addressof, sizeof
from time import sleep
from mcculw import ul
from mcculw.enums import ScanOptions, FunctionType, Status
from mcculw.device_info import DaqDeviceInfo
from multiprocessing import Barrier, Process
from tkinter import *
import pandas as pd
import numpy as np
import time, serial, os, sys

# -- If program log is included
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

# -- Begin processes for simultaneous data acquisition and save to file
def read_and_save(rate, buffer_size_seconds, save_option, file_name):

# -- If program log is included
# def read_and_save(rate, buffer_size_seconds, save_option, file_name, log):

    path = 'C:/Users/Kevin/Desktop/projects/daq/mcculw-master/examples/console/'

    # -- File name strings
    central_file_name = file_name + ' .csv'
    six_file_name = file_name + ' -- Chest Strap Piezos .csv'
    electrode_file_name = file_name + ' -- Electrodes .csv'
    two_file_name = file_name + ' -- Carotid and Femoral .csv'
    flex_file_name = file_name + ' -- Flex Sensor .csv'

    # -- If program log is included
    # Label(log, text="Scanning . . .", anchor='w').grid()

    print( '=================================================================\n')

    # -- Start processes for each device
    synchronizer = Barrier(3)
    simultaneous_for_6_piezos = Process(target=six_read, args=(synchronizer, rate, buffer_size_seconds,six_file_name))
    simultaneous_for_2_piezos = Process(target=two_read, args=(synchronizer, rate, buffer_size_seconds, two_file_name))
    simultaneous_for_flex = Process(target=flex_read, args=(synchronizer, buffer_size_seconds, flex_file_name))

    # -- Record data from ECG electrodes, acoustic and chest strap piezosensors
    simultaneous_for_6_piezos.start()

    # -- Record data from carotid and femoral artery piezosensors
    simultaneous_for_2_piezos.start()

    # -- Record data from the flex sensor
    simultaneous_for_flex.start()

    simultaneous_for_6_piezos.join()
    simultaneous_for_2_piezos.join()
    simultaneous_for_flex.join()

    # -- Save to CSV
    print('  Saving to file(s) . . .\n')

    # -- If program log is included
    # Label(log, text="Saving to file(s) . . .", anchor='w').grid()

    six_df = pd.read_csv(path + six_file_name)

    # -- Save to one file
    if save_option == 1:

        os.remove(path + six_file_name)

        two_df = pd.read_csv(path + two_file_name)
        flex_df = pd.read_csv(path + flex_file_name)
        
        os.remove(path + two_file_name)
        os.remove(path + flex_file_name)

        isolated_time_col = six_df['Time (s)'].to_frame()
        isolated_piezode_col = six_df[['Piezo Channel 0 (V)', 'Piezo Channel 1 (V)', 'Piezo Channel 2 (V)', 'Piezo Channel 3 (V)',	'Piezo Channel 4 (V)', 'Piezo Channel 5 (V)','Electrode (V)']]
        isolated_two_col = two_df[['Carotid Piezo (V)', 'Femoral Piezo (V)']]

        isolated_flex_col = flex_df['Angular Displacement (deg)']
        disc_flex_data = []
        reference_timestamp = [] 

        # -- Main time column
        increment = 0
        while increment <= buffer_size_seconds:
            reference_timestamp.append( increment )
            increment = float('{:.5f}'.format(increment + 1 / rate)) 

        # -- Split continuous flex sensor data
        index = 0
        for i in range(len(reference_timestamp)):
            if (float('{:.5f}'.format(reference_timestamp[i]*100))).is_integer():
                disc_flex_data.append(isolated_flex_col[index])
                index += 1
            else:
                disc_flex_data.append(' ')

        isolated_flex_col = pd.DataFrame(disc_flex_data, columns=['Angular Displacement (deg)'])

        # -- Join all data to one DataFrame
        central_df = isolated_time_col.join(isolated_two_col).join(isolated_piezode_col).join(isolated_flex_col)
        central_df.to_csv(central_file_name, index=False)

    # -- Save to multiple files
    else:

        # -- Separate ECG electrode data from acoustic and chest strap data
        isolated_columns = six_df[['Time (s)', 'Electrode (V)']]

        # -- Updating acoustic and chest strap DataFrame
        six_df.drop('Electrode (V)', axis=1, inplace=True)
        six_df.drop('Unnamed: 8', axis=1, inplace=True)
        six_df.to_csv(six_file_name, index=False)

        isolated_columns.to_csv(electrode_file_name, index=False)

    # -- If program log is included
    # Label(log, text="Save completed.", anchor='w').grid(pady=(0,5))

    print('  Save completed.\n\n')

# -- Data acquisition for ECG electrodes, acoustic and chest strap piezosensors
def six_read(synch, rate, buffer_size_seconds, six_file):

    # -- Wait for serial port connection to occur in the third process
    sleep(2.2)

    use_device_detection = True
    dev_id_list = []
    board_num = 1
    memhandle = None
    num_buffers_to_write = 1
    delay = 1 / rate
    
    # -- Configure DAQ device
    if use_device_detection:
        config_first_detected_device(board_num, dev_id_list)

    daq_dev_info = DaqDeviceInfo(board_num)
    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')

    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

    ai_info = daq_dev_info.get_ai_info()
    low_chan = 0
    high_chan = 6
    num_chans = high_chan - low_chan + 1

    points_per_channel = max(rate * buffer_size_seconds + 1, 10)

    if ai_info.packet_size != 1:
        packet_size = ai_info.packet_size
        remainder = points_per_channel % packet_size

        if remainder != 0:
            points_per_channel += packet_size - remainder

    ul_buffer_count = points_per_channel * num_chans

    # -- Write the UL buffer to the file, num_buffers_to_write times
    points_to_write = ul_buffer_count * num_buffers_to_write

    # -- When handling the buffer, we will read 7 data points from the buffer at a time
    write_chunk_size = int(ul_buffer_count / points_per_channel)
    
    try:
        ai_range = ai_info.supported_ranges[0]
    except IndexError:
        print('  ERROR: RECONNECT USB\n')
        sys.exit()

    scan_options = (ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS | ScanOptions.SCALEDATA)
    memhandle = ul.scaled_win_buf_alloc(ul_buffer_count)

    # -- Allocate an array of doubles for temporary storage of data
    write_chunk_array = (c_double * write_chunk_size)()

    # -- Check if the buffer was successfully allocated
    if not memhandle:
        raise Exception('Failed to allocate memory')
    
    # -- Initiate scan
    ul.a_in_scan( board_num, low_chan, high_chan, ul_buffer_count, rate, ai_range, memhandle, scan_options)
    status = Status.IDLE

    # -- Wait for the scan to start fully
    while status == Status.IDLE:
        status, _, _ = ul.get_status(board_num, FunctionType.AIFUNCTION)

    # -- Create a file for storing the data
    with open(six_file, 'w') as f:

        # -- Write a header to the file
        f.write('Time (s)' + ',')

        for chan_num in range(low_chan, high_chan):
            f.write('Piezo Channel ' + str(chan_num) + ' (V)'+ ',')

        f.write('Electrode (V)' + ',')    
        f.write(u'\n')

        # -- Start the write loop
        prev_count = 0
        prev_index = 0
        write_ch_num = low_chan

        # -- Wait for all device configurations/preparations to align in every process
        synch.wait()

        # print('---------- SIX START:     ', time.time())
        t=0

        # -- Main scan loop
        while status != Status.IDLE:

            # -- Get the latest counts
            status, curr_count, _ = ul.get_status(board_num, FunctionType.AIFUNCTION)
            new_data_count = curr_count - prev_count

            # -- Check for a buffer overrun before copying the data, so that no attempts are made to copy more than a full buffer of data
            if new_data_count > ul_buffer_count:
                ul.stop_background(board_num, FunctionType.AIFUNCTION)
                print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                break

            # -- Check if a chunk is available
            if new_data_count > write_chunk_size:

                wrote_chunk = True

                # -- Copy the current data to a new array

                # -- Check if the data wraps around the end of the UL buffer (multiple copy operations will be required)
                if prev_index + write_chunk_size > ul_buffer_count - 1:

                    first_chunk_size = ul_buffer_count - prev_index
                    second_chunk_size = ( write_chunk_size - first_chunk_size )
                    
                    # -- Copy the first chunk of data to the write_chunk_array
                    ul.scaled_win_buf_to_array( memhandle, write_chunk_array, prev_index, first_chunk_size)

                    # -- Create a pointer to the location in write_chunk_array where we want to copy the remaining data
                    second_chunk_pointer = cast(addressof(write_chunk_array)
                                                + first_chunk_size
                                                * sizeof(c_double),
                                                POINTER(c_double))

                    # -- Copy the second chunk of data to the write_chunk_array
                    ul.scaled_win_buf_to_array(
                        memhandle, second_chunk_pointer,
                        0, second_chunk_size)

                else:

                    # -- Copy the data to the write_chunk_array
                    ul.scaled_win_buf_to_array(
                        memhandle, write_chunk_array, prev_index,
                        write_chunk_size)
                
                # -- Check for a buffer overrun just after copying the data from the UL buffer
                #    This ensures that data was not overwritten in the UL buffer before the copy was completed. 
                #    This should be done before writing to the file, so that corrupt data does not end up in the file
                status, curr_count, _ = ul.get_status( board_num, FunctionType.AIFUNCTION )
                
                if curr_count - prev_count > ul_buffer_count:

                    # -- Print an error and stop writing
                    ul.stop_background(board_num, FunctionType.AIFUNCTION)
                    print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                    break

                f.write(str(t) + ',')
                t+=delay

                # -- Write to file
                for i in range(write_chunk_size):
                    f.write(str(write_chunk_array[i]) + ',')
                    write_ch_num += 1
                    if write_ch_num == high_chan + 1:
                        write_ch_num = low_chan
                        f.write(u'\n')
            else:
                wrote_chunk = False

            if wrote_chunk:
                # -- Increment prev_count by the chunk size
                prev_count += write_chunk_size

                # -- Increment prev_index by the chunk size
                prev_index += write_chunk_size

                # -- Wrap prev_index to the size of the UL buffer
                prev_index %= ul_buffer_count

                if prev_count >= points_to_write:
                    break

            else:
                # -- Wait a short amount of time for more data to be acquired.
                sleep(0.1)

    # print('---------- SIX DONE:     ', time.time())

    ul.stop_background(board_num, FunctionType.AIFUNCTION)

    if memhandle:
        # -- Free the buffer in a finally block to prevent  a memory leak.
        ul.win_buf_free(memhandle)

    if use_device_detection:
        # -- Disconnect the DAQ device
        ul.release_daq_device(board_num)

# -- Data acquisition for carotid and femoral artery piezosensors 
def two_read(synch, rate, buffer_size_seconds, two_file):

    sleep(2.2)
    use_device_detection = True
    dev_id_list = []
    board_num = 0
    memhandle = None
    num_buffers_to_write = 1
    delay = 1 / rate
    
    if use_device_detection:
        config_first_detected_device(board_num, dev_id_list)

    daq_dev_info = DaqDeviceInfo(board_num)

    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')

    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

    ai_info = daq_dev_info.get_ai_info()
    low_chan = 0
    high_chan = 1
    num_chans = high_chan - low_chan + 1

    points_per_channel = max(rate * buffer_size_seconds + 1, 10)

    if ai_info.packet_size != 1:
        packet_size = ai_info.packet_size
        remainder = points_per_channel % packet_size

        if remainder != 0:
            points_per_channel += packet_size - remainder

    ul_buffer_count = points_per_channel * num_chans
    points_to_write = ul_buffer_count * num_buffers_to_write
    write_chunk_size = int(ul_buffer_count / points_per_channel)

    try:
        ai_range = ai_info.supported_ranges[0]
    except IndexError:
        print('  ERROR: RECONNECT USB\n')
        sys.exit()

    scan_options = (ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS | ScanOptions.SCALEDATA)
    memhandle = ul.scaled_win_buf_alloc(ul_buffer_count)

    write_chunk_array = (c_double * write_chunk_size)()

    if not memhandle:
        raise Exception('Failed to allocate memory')

    ul.a_in_scan( board_num, low_chan, high_chan, ul_buffer_count, rate, ai_range, memhandle, scan_options)
    status = Status.IDLE

    while status == Status.IDLE:
        status, _, _ = ul.get_status(board_num, FunctionType.AIFUNCTION)

    with open(two_file, 'w') as f:

        f.write('Time (s)' + ',')
        f.write('Carotid Piezo (V)' + ',')  
        f.write('Femoral Piezo (V)' + ',')    
        f.write(u'\n')

        prev_count = 0
        prev_index = 0
        write_ch_num = low_chan   

        synch.wait()

        # ('---------- TWO START:     ', time.time())
        t=0

        while status != Status.IDLE:

            status, curr_count, _ = ul.get_status( board_num, FunctionType.AIFUNCTION )
            new_data_count = curr_count - prev_count

            if new_data_count > ul_buffer_count:
                ul.stop_background(board_num, FunctionType.AIFUNCTION)
                print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                break

            if new_data_count > write_chunk_size:
                wrote_chunk = True

                if prev_index + write_chunk_size > ul_buffer_count - 1:

                    first_chunk_size = ul_buffer_count - prev_index
                    second_chunk_size = ( write_chunk_size - first_chunk_size )

                    ul.scaled_win_buf_to_array(
                        memhandle, write_chunk_array, prev_index,
                        first_chunk_size)

                    second_chunk_pointer = cast(addressof(write_chunk_array)
                                                + first_chunk_size
                                                * sizeof(c_double),
                                                POINTER(c_double))

                    ul.scaled_win_buf_to_array(
                        memhandle, second_chunk_pointer,
                        0, second_chunk_size)
                else:
                    ul.scaled_win_buf_to_array(
                        memhandle, write_chunk_array, prev_index,
                        write_chunk_size)

                status, curr_count, _ = ul.get_status( board_num, FunctionType.AIFUNCTION )

                if curr_count - prev_count > ul_buffer_count:

                    ul.stop_background(board_num, FunctionType.AIFUNCTION)
                    print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                    break

                f.write(str(t) + ',')
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

                prev_count += write_chunk_size
                prev_index += write_chunk_size
                prev_index %= ul_buffer_count

                if prev_count >= points_to_write:
                    break
            else:
                sleep(0.1)

    #print('---------- TWO DONE:     ', time.time())

    ul.stop_background(board_num, FunctionType.AIFUNCTION)

    if memhandle:
        ul.win_buf_free(memhandle)

    if use_device_detection:
        ul.release_daq_device(board_num)

# -- Data acquisition for flex sensor
def flex_read(synch, buffer_size_seconds, flex_file):

    # -- Establish serial port connection
    ser = serial.Serial('COM3', 115200, timeout=1)
    ser.flushInput()

    # -- Readline until successful connection indicator is removed
    temp_scan = ""
    while temp_scan != "One Axis ADS initialization succeeded...":
        temp_scan = ser.readline()
        try:
            temp_scan = temp_scan.decode("utf-8")
            temp_scan = temp_scan[:-2]
        except UnicodeDecodeError:
            pass

    print('  Flex Sensor: Connected to COM3 at 115200 baud\n')

    digital_data = np.array([])
    flex_timestamp = np.array([])
    print('  Scanning . . .\n')

    synch.wait()

    #print( ' --------- FLEX START: ', time.time())

    # -- Begin scan for duration
    te = time.time() + buffer_size_seconds

    while time.time() <= te:
        digital_data = np.append(digital_data, ser.readline().decode('utf-8'))
        
    print('  Scan completed in', '{:.1f}'.format(time.time() - (te - buffer_size_seconds)), 'seconds. \n')   

    # -- Close serial port connection
    ser.close()
    del ser

    # -- Catch slight time error
    if(len(digital_data) != 100 * buffer_size_seconds + 1):
        print('  ERROR: FLEX SENSOR DATA ACQUISITION FAILED. RUN THE SCAN AGAIN.\n')
        sys.exit()

    # -- Process acquired data
    increment = 0
    for i in range(len(digital_data)):
        digital_data[i] = digital_data[i].strip()

    # -- Create timestamp column for flex sensor
    increment = 0
    while increment <= buffer_size_seconds:
        flex_timestamp = np.append(flex_timestamp, increment)
        increment = float('{:.5f}'.format(increment + 0.01))

    # -- Export to temporary CSV
    temp_df = pd.DataFrame({'Time (s)' : flex_timestamp, 'Angular Displacement (deg)': digital_data})
    temp_df.to_csv(flex_file, index=False)
