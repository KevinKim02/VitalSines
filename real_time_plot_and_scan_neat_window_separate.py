'''
    Interactive GUI window with real-time plot and data acquisition functionalities (not concurrently)
    
'''


from __future__ import absolute_import, division, print_function
from builtins import *
from mcculw import ul
from mcculw.enums import ScanOptions, FunctionType, Status
from mcculw.device_info import DaqDeviceInfo
from ctypes import c_double, cast, POINTER, addressof, sizeof

from multiprocessing import Barrier, Lock, Process
from threading import Thread
from time import sleep, time
from datetime import datetime
from tkinter import *

import collections, sys, serial, os
import pandas as pd
import numpy as np
try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QThread

anim0 = ''
anim1 = ''
animQ = ''
pause = False

class DAQ():
    def __init__(self, bn, lchn, hchn):
        # scan inits
        self.use_device_detection = True
        self.dev_id_list = []
        self.board_num = bn
        self.rate = 100
        self.buffer_size_seconds = 10
        self.memhandle = None
        self.num_buffers_to_write = 1
        self.delay = 1 / self.rate

        if self.use_device_detection:
            config_first_detected_device(self.board_num, self.dev_id_list)
        daq_dev_info = DaqDeviceInfo(self.board_num)
        if not daq_dev_info.supports_analog_input:
            raise Exception('Error: The DAQ device does not support analog input')
        print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')

        self.ai_info = daq_dev_info.get_ai_info()
        self.low_chan = lchn
        self.high_chan = hchn
        self.num_chans = self.high_chan - self.low_chan + 1

        self.points_per_channel = max(self.rate * self.buffer_size_seconds + 1, 10)

        if self.ai_info.packet_size != 1:
            self.packet_size = self.ai_info.packet_size
            self.remainder = self.points_per_channel % self.packet_size
            if self.remainder != 0:
                self.points_per_channel += self.packet_size - self.remainder

        self.ul_buffer_count = self.points_per_channel * self.num_chans
        # Write the UL buffer to the file num_buffers_to_write times.
        self.points_to_write = self.ul_buffer_count * self.num_buffers_to_write
        # When handling the buffer, we will read 1/10 of the buffer at a time
        self.write_chunk_size = int(self.ul_buffer_count / self.points_per_channel)

        try:
            self.ai_range = self.ai_info.supported_ranges[0]
        except IndexError:
            print('  ERROR: RECONNECT USB\n')
            sys.exit()

        self.scan_options = (ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS | ScanOptions.SCALEDATA)
        self.memhandle = ul.scaled_win_buf_alloc(self.ul_buffer_count)
        # Allocate an array of doubles temporary storage of the data
        self.write_chunk_array = (c_double * self.write_chunk_size)()
        # Check if the buffer was successfully allocated
        if not self.memhandle:
            raise Exception('Failed to allocate memory')

        # plot inits
        self.data = collections.deque([0] * 100, maxlen=100)
        self.plotMaxLength = 100

    def save_get_value(self, frame, lines):
        self.data.append(self.write_chunk_array[0])
        lines.set_data(range(self.plotMaxLength), self.data)

    def six_read(self): #synch
        ul.a_in_scan( self.board_num, self.low_chan, self.high_chan, self.ul_buffer_count, self.rate, self.ai_range, self.memhandle, self.scan_options)
        status = Status.IDLE

        # Wait for the scan to start fully
        while status == Status.IDLE:
            status, _, _ = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
        
        # Create a file for storing the data
        with open( datetime.now().strftime('%Y-%m-%d %H;%M;%S') + ' .csv', 'w') as f:
            # Write a header to the file
            f.write('Time (s)' + ',')
            for chan_num in range(self.low_chan, self.high_chan):
                f.write('Piezo Channel ' + str(chan_num) + ' (V)'+ ',')
            f.write('Electrode (V)' + ',')    
            f.write(u'\n')

            # Start the write loop
            prev_count = 0
            prev_index = 0
            write_ch_num = self.low_chan

            #synch.wait()
            print('---------- SIX START:     ', time())

            t=0
            while status != Status.IDLE:
                # Get the latest counts
                status, curr_count, _ = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
                new_data_count = curr_count - prev_count

                # Check for a buffer overrun before copying the data, so that no attempts are made to copy more than a full buffer of data
                if new_data_count > self.ul_buffer_count:
                    ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
                    print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                    break

                # Check if a chunk is available
                if new_data_count > self.write_chunk_size:
                    wrote_chunk = True

                    # Copy the current data to a new array and check if the data wraps around the end of the UL buffer. Multiple copy operations will be required.
                    if prev_index + self.write_chunk_size > self.ul_buffer_count - 1:
                        first_chunk_size = self.ul_buffer_count - prev_index
                        second_chunk_size = (self.write_chunk_size - first_chunk_size)

                        # Copy the first chunk of data to the write_chunk_array
                        ul.scaled_win_buf_to_array(self.memhandle, self.write_chunk_array, prev_index,first_chunk_size)

                        # Create a pointer to the location in write_chunk_array where we want to copy the remaining data
                        second_chunk_pointer = cast(addressof(self.write_chunk_array) + first_chunk_size * sizeof(c_double), POINTER(c_double))

                        # Copy the second chunk of data to the write_chunk_array
                        ul.scaled_win_buf_to_array(self.memhandle, second_chunk_pointer,0, second_chunk_size)

                    # Copy the data to the write_chunk_array
                    else:
                        ul.scaled_win_buf_to_array(self.memhandle, self.write_chunk_array, prev_index,self.write_chunk_size)

                    #self.data.append(self.write_chunk_array[0])
                    #lines0.set_data(range(self.plotMaxLength), self.data)
                
                    # Check for a buffer overrun just after copying the data from the UL buffer. This will ensure that the data was not overwritten in the UL buffer before the copy was
                    # completed. This should be done before writing to the file, so that corrupt data does not end up in it.
                    status, curr_count, _ = ul.get_status(self.board_num, FunctionType.AIFUNCTION)

                    if curr_count - prev_count > self.ul_buffer_count:
                        # Print an error and stop writing
                        ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
                        print('  ERROR: A BUFFER OVERRUN OCCURRED\n')
                        break
                    f.write(str(t) + ',')
                    t+=self.delay

                    for i in range(self.write_chunk_size):
                        f.write(str(self.write_chunk_array[i]) + ',')
                        write_ch_num += 1
                        if write_ch_num == self.high_chan + 1:
                            write_ch_num = self.low_chan
                            f.write(u'\n')
                else:
                    wrote_chunk = False
                if wrote_chunk:
                    # Increment prev_count by the chunk size
                    prev_count += self.write_chunk_size
                    # Increment prev_index by the chunk size
                    prev_index += self.write_chunk_size
                    # Wrap prev_index to the size of the UL buffer
                    prev_index %= self.ul_buffer_count
                    if prev_count >= self.points_to_write:
                        break
                else:
                    # Wait a short amount of time for more data to be acquired.
                    sleep(0.1)

        print('---------- SIX DONE:     ', time())
        ul.stop_background(self.board_num, FunctionType.AIFUNCTION)

    def plot_get_value(self, frame, lines, ch):
        if self.ai_info.resolution <= 16:
            # Use the a_in method for devices with a resolution <= 16
            raw_value = ul.a_in(self.board_num, ch, self.ai_range)
            value = ul.to_eng_units(self.board_num, self.ai_range, raw_value)
        else:
            # Use the a_in_32 method for devices with a resolution > 16
            raw_value = ul.a_in_32(self.board_num, ch, self.ai_range)
            value= ul.to_eng_units_32(self.board_num, self.ai_range, raw_value)
         
        self.data.append(value)    # we get the latest data point and append it to our array
        lines.set_data(range(self.plotMaxLength), self.data)

    def close(self):
        if self.memhandle:
            # Free the buffer in a finally block to prevent  a memory leak.
            ul.win_buf_free(self.memhandle)
        if self.use_device_detection:
            ul.release_daq_device(self.board_num)
        print('DONE DONE DONE DONE DONE')

def onClick(event):
    global pause
    pause ^= True

def animate():
    global animQ
    print('here')
    animQ = animation.FuncAnimation(fig, d1.save_get_value, fargs=(lines0,), interval=100)
    fig.canvas.draw()

class ScrollableWindow(QtWidgets.QMainWindow):
    def __init__(self, fig):
        self.qapp = QtWidgets.QApplication([])

        QtWidgets.QMainWindow.__init__(self)
        self.widget = QtWidgets.QWidget()
        self.setCentralWidget(self.widget)
        self.widget.setLayout(QtWidgets.QVBoxLayout())
        self.widget.layout().setContentsMargins(0,0,0,0)
        self.widget.layout().setSpacing(0)

        self.fig = fig
        self.canvas = FigureCanvas(self.fig)

        self.canvas.draw()
        self.scroll = QtWidgets.QScrollArea(self.widget)
        self.scroll.setWidget(self.canvas)

        self.nav = NavigationToolbar(self.canvas, self.widget)
        self.widget.layout().addWidget(self.nav)
        self.widget.layout().addWidget(self.scroll)

        self.title = 'PyQt5 button - pythonspot.com'
        self.left = 10
        self.top = 10
        self.width = 320
        self.height = 200
        self.initUI()

        self.showMaximized()
        self.show()
        exit(self.qapp.exec_()) 
    
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        button = QPushButton('Record', self)
        button.setToolTip('This is an example button')
        button.resize(200,50)
        button.move(400,700)
        button.clicked.connect(self.on_scan_click)

        button1 = QPushButton('Plot', self)
        button1.setToolTip('This is an example button')
        button1.resize(200,50)
        button1.move(700,700)
        button1.clicked.connect(self.on_plot_click)

        button2 = QPushButton('Save', self)
        button2.setToolTip('This is an example button')
        button2.resize(200,50)
        button2.move(1000,700)
        button2.clicked.connect(self.on_save_click)

        self.show()

    @pyqtSlot()
    def on_plot_click(self):
        live_plot()

    @pyqtSlot()
    def on_scan_click(self):
        animations = [anim0, anim1]
        for anim in animations:
            anim.event_source.stop()
        d1.six_read()

    @pyqtSlot()
    def on_save_click(self):
        print('HI')

    def closeEvent(self, event):
        d1.close()
        event.accept()


if __name__ == '__main__':
    # create a figure and some subplots
    fig, (ax0, ax1) = plt.subplots(ncols=2, nrows=1, sharex=True, sharey='row', figsize=(16,5))

    ax0.set_xlim([0, 100])
    ax0.set_ylim([-3,3])
    ax1.set_xlim([0, 100])

    lineLabel0 = 'Carotid Piezo'
    lines0 = ax0.plot([], [], label=lineLabel0, linewidth=0.5)[0]

    lineLabel1 = 'Femoral Piezo'
    lines1 = ax1.plot([], [], label=lineLabel1, linewidth=0.5)[0]
    
    axes = [ax0, ax1]
    for ax in axes:
        ax.legend(loc="upper left")
    fig.tight_layout()

    # instantiate DAQ
    d1 = DAQ(0, 0, 6)
 
    def live_plot():
        global anim0, anim1
        anim0 = animation.FuncAnimation(fig, d1.plot_get_value, fargs=(lines0, 0), interval=100) 
        anim1 = animation.FuncAnimation(fig, d1.plot_get_value, fargs=(lines1, 1), interval=100)
        fig.canvas.draw()

    # pass the figure to the custom window
    a = ScrollableWindow(fig)




