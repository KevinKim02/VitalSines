'''
    Real-time plot with pause/resume functionality when window is clicked
    
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
#import pandas as pd

try:
    from console_examples_util import config_first_detected_device
except ImportError:
    from .console_examples_util import config_first_detected_device

pause = False

class DAQ:
    def __init__(self, ch, bn, ddi):
        self.use_device_detection = True
        self.dev_id_list = []
        self.board_num = bn
        self.rate = 1000
        self.memhandle = None
        self.data = collections.deque([0] * 100, maxlen=100)
        self.plotTimer = 0
        self.previousTimer = 0
        self.plotMaxLength = 100

        self.ai_info = ddi.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]
        self.channel = ch
    
    def get_value(self, frame, lines, timeText):
        if not pause:
            if self.ai_info.resolution <= 16:
                raw_value = ul.a_in(self.board_num, self.channel, self.ai_range)
                value = ul.to_eng_units(self.board_num, self.ai_range, raw_value)
            else:
                raw_value = ul.a_in_32(self.board_num, self.channel, self.ai_range)
                value= ul.to_eng_units_32(self.board_num, self.ai_range, raw_value)

            currentTimer = time.perf_counter()
            self.plotTimer = int((currentTimer - self.previousTimer) * 1000)     # the first reading will be erroneous
            self.previousTimer = currentTimer
            timeText.set_text('Plot Interval = ' + str(self.plotTimer) + 'ms')  

            self.data.append(value)    # we get the latest data point and append it to our array
            lines.set_data(range(self.plotMaxLength), self.data)


    def close(self):
        if self.use_device_detection:
            ul.release_daq_device(self.board_num)

daq_instance = [None] * 1

def inst0():
    config_first_detected_device(0, [])
    daq_dev_info = DaqDeviceInfo(0)
    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')
    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')
    daq_instance[0] = DAQ(0,0, daq_dev_info)
    time.sleep(0.1)

def inst1():
    config_first_detected_device(1, [])
    daq_dev_info = DaqDeviceInfo(1)
    if not daq_dev_info.supports_analog_input:
        raise Exception('Error: The DAQ device does not support analog input')
    print('  Active DAQ device: ', daq_dev_info.product_name, ' (', daq_dev_info.unique_id, ')\n', sep='')
    daq_instance[2] = DAQ(0,1, daq_dev_info)
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

def onClick(event):
    global pause
    pause ^= True

def plot_piezos():
    # --- Object Instantiation
    for_board0 = Thread(target=inst0)
    inst1()
    for_board0.start()
    for_board0.join()
    board_zero_ch_zero = daq_instance[0]

    # -- GRAPH CONFIG
    pltInterval = 10
    fig, (ax0) = plt.subplots(nrows=1, ncols=1, sharex=True, sharey='row', figsize=(20,8))
    ax0.set_xlim([0, 100])
    ax0.set_ylim([-3,3])
    fig.canvas.mpl_connect('button_press_event', onClick)

    # --- LIVE PLOT
    lineLabel = 'Carotid Piezo'
    timeText = ax0.text(0.50, 0.95, '', transform=ax0.transAxes)
    lines = ax0.plot([], [], label=lineLabel, linewidth=0.5)[0]
    anim = animation.FuncAnimation(fig, board_zero_ch_zero.get_value, fargs=(lines,timeText), interval=pltInterval) 

    # --- BRING UP GRID
    fig.tight_layout()
    ax0.legend(loc="upper left")
    mng = plt.get_current_fig_manager()
    mng.window.showMaximized()
    plt.show()

    # --- DELETION
    try:
        board_zero_ch_zero.close()
        del board_zero_ch_zero
        print('  Successfully disconnected.\n\n')
    except:
        print('  ERROR: DISCONNECTION FAILURE\n')
        sys.exit()

if __name__ == '__main__':
    plot_piezos()