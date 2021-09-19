'''
    Windows program capable of simultaneous data acquisition and post-scan data visualization from two DAQ devices and the serial port (USB-1608fs-Plus)
    Optional sampling rates (excluding the serial port, 100Hz), recording durations, and file save options (single/multiple spreadsheets)
    Real-time plotting feature from all data inputs at any desired time base (cannot run simultaneously with scan)  
    Prompts GUI window for user-entries and selections (recording duration, sampling rate, open spreadsheet, plot data, real-time plot)
    Recommended to run program GUI window concurrently with command prompt, Git Bash, or Windows PowerShell terminal to display the log
    Program prompts GUI window for user-entries (recording duration, sampling rate, open spreadsheet, plot data, real-time plot).
    Program log not implemented in GUI window.

    Hardware Setup at the Time of Program Development:
     - 6 custom piezoelectric sensors connected to 6 analog input channels of a USB-1608fs-Plus device
     - 2 HK-2000B piezoelectric sensors connected to 2 analog input channels of another USB-1608fs-Plus device
     - 1 Bend Labs digital one-axis flex sensor connected to an Arduino Due
     - USB hub for combining connections from Arduino Due and 2 USB-1608fs-Plus devices to 1 USB input into the Windows PC
    
    Software Setup at the Time of Program Development:
    - Uploaded bend_polled_demo.ino to the Arduino Due using Arduino IDE v1.8.15 for flex sensor configuration prior to scanning 
      (see bend_polled_demo folder in the repository for the uploaded code and dependencies)
    - InstaCal downloaded for USB-1608fs-Plus device configuration (https://www.mccdaq.com/daq-software/instacal.aspx)

    - Installed Software:
        Python 3.9.2
        pip 21.1.3
        matplotlib 3.4.2
        mcculw 1.0.0
        numpy 1.21.0
        pandas 1.2.4
        PyQt5 5.15.4
        PyQt5-Qt5 5.15.2
        PyQt5-sip 12.9.0
        pyserial 3.5

    - Imported Scripts:
        console_examples_util.py
        live_scan.py
        live_plot.py
        live_plot_flexode.py

'''

from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport
from tkinter import *
from datetime import datetime
from matplotlib.widgets import CheckButtons
from live_scan import read_and_save
import live_plot as piezos
import live_plot_flexode as flexode
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
import pandas as pd
import os

if __name__ == "__main__":

    print('\n\n')

    # -- File location for saving data spreadsheet
    path = os.getcwd() + '/'

    # -- Data spreadsheet file name
    fn = ''

    # -- Scan status indicator (program has started, first scan not started yet)
    done_scan = 0
    
    # -- tkinter window settings
    window = Tk()
    window.title("Scan")
    window.state('zoomed')

    # -- tkinter window frame layout
    frame_scan_header = Frame(window)               # 0 row / 0 col
    frame_scan_fields = Frame(window)               # 1 row / 0 col
    frame_scan = Frame(window)                      # 1 row / 1 col
    frame_live_header = Frame(window)               # 2 row / 0 col  
    frame_live_fields = Frame(window)               # 3 row / 0 col
    frame_live = Frame(window)                      # 3 row / 1 col
    frame_post_scan_header = Frame(window)          # 4 row / 0 col
    frame_open = Frame(window)                      # 5 row / 0 col
    frame_plot = Frame(window)                      # 5 row / 1 col

    # -- If program log is included
    # frame_log_header = Frame(window)               # 0 row / 2 col
    # frame_log = Frame(window)                      # 6 row / 3 col

    # -- User-entry fields for simultaneous data acquisition scan
    frame_scan_header.grid(row=0, column=0, pady=10)

    rt_plot_lbl = Label(frame_scan_header, text="Main Scan:", font=16)      
    rt_plot_lbl.grid(column=0, row=0)

    # -- Patient name
    frame_scan_fields.grid(row=1, column=0)
    full_name_lbl = Label(frame_scan_fields, text="Enter the full name: ")
    full_name_lbl .grid(column=0, row=0, pady=20)
    full_name_unparsed = Entry(frame_scan_fields,width=10)
    full_name_unparsed.grid(column=1, row=0, pady=20)

    # -- Patient sex
    sex_lbl = Label(frame_scan_fields, text="Enter the sex (M/F): ")
    sex_lbl.grid(column=0, row=1)
    sex_entry = StringVar(value='M')
    Radiobutton(frame_scan_fields, text='Male',variable=sex_entry, value='M').grid(column=1, row=1, sticky='W', padx=(10,0))
    Radiobutton(frame_scan_fields, text='Female',variable=sex_entry, value='F').grid(column=1, row=2, sticky='W', padx=(10,0), pady=(0,10))

    # -- Sampling rate
    rate_lbl = Label(frame_scan_fields, text="Enter the rate (scans/s): ")
    rate_lbl.grid(column=0, row=3)
    rate_unparsed = Entry(frame_scan_fields,width=10)
    rate_unparsed.grid(column=1, row=3)

    # -- Recording duration
    duration_lbl = Label(frame_scan_fields, text="Enter the duration (s): ")
    duration_lbl.grid(column=0, row=4, pady=20)
    duration = Entry(frame_scan_fields,width=10)
    duration.grid(column=1, row=4, pady=20)

    # -- File save option
    frame_scan.grid(row=1, column=1, padx=10, pady=0)
    file_save_entry = IntVar(value=1)
    Radiobutton(frame_scan, text='Save Data to One File',variable=file_save_entry, value=1).grid(column=0, row=0, sticky='W')
    Radiobutton(frame_scan, text='Save Data to Separate Files',variable=file_save_entry, value=2).grid(column=0, row=1, sticky='W')

    # -- User-entry fields for real-time plotting
    frame_live_header.grid(row=2, column=0, pady=(10,0))
    rt_plot_lbl = Label(frame_live_header, text="Real Time Plot:", font=16)      
    rt_plot_lbl.grid(column=0, row=0)

    # -- Time base
    frame_live_fields.grid(row=3, column=0, pady=(20,0), padx=(10,0))
    timebase_lbl = Label(frame_live_fields, text="Enter the delay between frames (ms): ") #0.1, 1
    timebase_lbl.grid(column=2, row=0)
    timebase_unparsed = Entry(frame_live_fields,width=10)
    timebase_unparsed.grid(column=3, row=0)

    Label(frame_live_fields, text='Ideally ~100ms (All Piezosensors)').grid(column=2, row=1, pady=(10,1))
    Label(frame_live_fields, text='Ideally ~50ms (Electrode, Flex Sensor)').grid(column=2, row=2, padx=(7,0))

    # -- Check validity of user-entries before starting the scan
    def pre_scan_check():

        if not rate_unparsed.get().isdigit():
            print('  Enter an integer for the rate.\n')
            return
        if not duration.get().isdigit():
            print('  Enter an integer for the duration.\n')
            return
        if int(rate_unparsed.get()) < 200:
            print('  Enter a rate greater than 200 scans/sec.\n')
            return
        if int(duration.get()) <= 0:
            print('  Enter a duration greater than 0 seconds.\n')
            return
        
        # -- Update data spreadsheet file name
        global fn
        fn = datetime.now().strftime('%Y-%m-%d %H;%M;%S') + ' -- ' + full_name_unparsed.get() + ' (' + sex_entry.get() + ') -- ' + rate_unparsed.get() + 'Hz for ' + duration.get() + 's'
        
        # -- Update scan status (scan in progress)
        global done_scan
        done_scan = -1

        # -- If entries are valid, begin scan
        read_and_save(int(rate_unparsed.get()), int(duration.get()), int(file_save_entry.get()), fn)#, frame_log)
        
        # -- If program log is included
        # read_and_save(int(rate_unparsed.get()), int(duration.get()), int(file_save_entry.get()), fn, frame_log)

        # -- Update scan status (scan complete)
        done_scan = 1
        
        return

    # -- Check validity of user-entries before plotting real-time data
    def pre_live_check():

        if not timebase_unparsed.get().isdigit():
            print('  Enter an integer for the time base.\n')
            return False
        if int(timebase_unparsed.get()) <= 0:
            print('  Enter an integer greater than 0 for the time base.\n')
            return False
        else:
            return True

    # -- Real-time plot for carotid artery, femoral artery, acoustic, chest strap piezosensors
    def real_time_plot_piezos():
        
        if pre_live_check():
            piezos.plot_piezos(int(timebase_unparsed.get()))
            
            # -- If program log is included
            # piezos.plot_piezos(int(timebase_unparsed.get()), frame_log)
        return

    # -- Real-time plot for ECG electrodes and flex sensor
    def real_time_plot_flexode():

        if pre_live_check():
            flexode.plot_flexode(int(timebase_unparsed.get()))

            # -- If program log is included
            # flexode.plot_flexode(int(timebase_unparsed.get()), frame_log)
        return
    
    # -- Open spreadsheet containing all data
    def open_central():

        # -- Block request if scan status is not complete
        if done_scan < 1:
            return

        # -- Block request if option for saving to multiple files was selected
        if int(file_save_entry.get()) == 2:
            pass
        # -- Option for saving to one file was selected
        else:
            os.startfile(path + fn + ' .csv')

    # -- Open spreadsheet containing acoustic and chest strap piezosensor data
    def open_piezos():

        # -- Block request if scan status is not complete
        if done_scan < 1:
            return

        # -- Block request if option for saving to one file was selected
        if int(file_save_entry.get()) == 1:
            pass

        # -- Option for saving to multiple files was selected
        else:
            os.startfile(path + fn + ' -- Chest Strap Piezos .csv' )
    
    # -- Open spreadsheet containing carotid and femoral artery piezosensor data
    def open_carotid():

        if done_scan < 1:
            return

        if int(file_save_entry.get()) == 1:
            pass

        else:
            os.startfile(path + fn + ' -- Carotid and Femoral .csv')

    # -- Open spreadsheet containing ECG electrode data
    def open_electr():

        if done_scan < 1:
            return

        if int(file_save_entry.get()) == 1:
            pass

        else:
            os.startfile(path + fn + ' -- Electrodes .csv')

    # -- Open spreadsheet containing flex sensor data
    def open_flex():

        if done_scan < 1:
            return

        if int(file_save_entry.get()) == 1:
            pass

        else:
            os.startfile(path + fn + ' -- Flex Sensor .csv')

    # -- Post-scan plot data from acoustic and chest strap piezosensors
    def post_plot_piezo():

        # -- Block request if scan status is not complete
        if done_scan < 1:
            return

        else:
            # -- Recording duration
            buffer_size_seconds = int(duration.get())

            # -- Plot window settings
            plot_window = plt.get_current_fig_manager()
            plot_window.window.showMaximized()

            # -- Graph settings
            plt.axes()
            plt.title('Piezosensor Output (Chest Strap, Channel 0-5)', loc='center', pad=16 )

            plt.xlabel('Time (s)')
            plt.xlim([0,buffer_size_seconds])

            plt.ylabel('Amplitude (V)')
            plt.ylim([0, 10])

            # -- Load appropriate spreadsheet depending on file save option
            if file_save_entry.get() == 1:
                df = pd.read_csv(path + fn  + ' .csv') 
            else:
                df = pd.read_csv(path + fn + ' -- Chest Strap Piezos .csv')

            # -- Create plots for each piezosensor channel
            ch0, = plt.plot(df['Time (s)'], df['Piezo Channel 0 (V)'], label='CH0', linewidth=0.5, color='r')
            ch1, = plt.plot(df['Time (s)'], df['Piezo Channel 1 (V)'], label='CH1', linewidth=0.5, color='y')
            ch2, = plt.plot(df['Time (s)'], df['Piezo Channel 2 (V)'], label='CH2', linewidth=0.5, color='g')
            ch3, = plt.plot(df['Time (s)'], df['Piezo Channel 3 (V)'], label='CH3', linewidth=0.5, color='b')
            ch4, = plt.plot(df['Time (s)'], df['Piezo Channel 4 (V)'], label='CH4', linewidth=0.5, color='c')
            ch5, = plt.plot(df['Time (s)'], df['Piezo Channel 5 (V)'], label='CH5', linewidth=0.5, color='m')

            channel = [ch0, ch1, ch2, ch3, ch4, ch5]

            # -- Area for channel buttons
            plt.subplots_adjust(left=0.1, bottom=0.1, right=0.95, top=0.95)

            # -- Display graphs of all piezosensor channels when first loaded
            label_on = [True, True, True, True, True, True] 
            label = ['CH0','CH1','CH2','CH3', 'CH4', 'CH5']

            # -- Each channel button area    
            button_space = plt.axes([0.92, 0.4, 0.15, 0.15])
            button = CheckButtons(button_space, label, label_on)

            # -- Show/hide graph of a channel upon button click
            def set_visible(labels):
                i = label.index(labels)
                channel[i].set_visible(not channel[i].get_visible())
                plt.draw()  

            # -- Set the button colour to make channels distinguishable    
            [rec.set_facecolor(channel[i].get_color()) for i, rec in enumerate(button.rectangles)]

            button.on_clicked(set_visible)

            # -- Load main plot window
            plt.show()

    # -- Post-scan plot data from carotid and femoral artery piezosensors
    def post_plot_carotid():

        if done_scan < 1:
            return

        else:

            buffer_size_seconds = int(duration.get())

            plot_window = plt.get_current_fig_manager()
            plot_window.window.showMaximized()

            plt.axes()
            plt.title('Piezosensor Output (Carotid and Femoral)', loc='center', pad=16 )

            plt.xlabel('Time (s)')
            plt.xlim([0,buffer_size_seconds])

            plt.ylabel('Amplitude (V)')
            plt.ylim([-5, 5])

            if file_save_entry.get() == 1:
                df = pd.read_csv(path + fn  + ' .csv') 
            else:
                df = pd.read_csv(path + fn + ' -- Carotid and Femoral .csv')

            ch0, = plt.plot(df['Time (s)'], df['Carotid Piezo (V)'], label='Carotid', linewidth=0.5, color='r')
            ch1, = plt.plot(df['Time (s)'], df['Femoral Piezo (V)'], label='Femoral', linewidth=0.5, color='b')

            channel = [ch0, ch1]

            plt.subplots_adjust(left=0.1, bottom=0.1, right=0.95, top=0.95)

            label_on = [True, True]
            label = ['Carotid','Femoral']     
            button_space = plt.axes([0.92, 0.4, 0.15, 0.15])
            button = CheckButtons(button_space, label, label_on)

            def set_visible(labels):
                i = label.index(labels)
                channel[i].set_visible(not channel[i].get_visible())
                plt.draw()     

            [rec.set_facecolor(channel[i].get_color()) for i, rec in enumerate(button.rectangles)]

            button.on_clicked(set_visible)

            plt.show()
            
    # -- Post-scan plot data from ECG electrodes
    def post_plot_electrode():

        if done_scan < 1:
            return

        else:

            buffer_size_seconds = int(duration.get())

            plot_window = plt.get_current_fig_manager()
            plot_window.window.showMaximized()

            plt.axes()
            plt.title('Electrode Output', loc='center', pad=16)
            
            plt.xlabel('Time (s)')
            plt.xlim([0,buffer_size_seconds])

            plt.ylabel('Amplitude (V)')
            plt.ylim([-2,6])

            if file_save_entry.get() == 1:
                df = pd.read_csv(path + fn  + ' .csv') 
            else:
                df = pd.read_csv(path + fn + ' -- Electrodes .csv')

            # -- Single plot
            plt.plot(df['Time (s)'], df['Electrode (V)'], linewidth=0.6, color='r') 

            plt.show()

    # -- Post-scan plot data from flex sensor
    def post_plot_flex():

        if done_scan < 1:
            return

        else:

            buffer_size_seconds = int(duration.get())
            
            # -- Data spreadsheet saved to one file
            if file_save_entry.get() == 1:
    
                df1 = pd.read_csv(path + fn  + ' .csv') 

                # -- Contains discrete data (data split with empty values to match with continuous time column at higher sampling rate)
                disc_iso = df1['Angular Displacement (deg)']

                # -- Continuous data with no empty values in between
                flex_iso = []

                # -- Linear search through discrete dataset
                for i in range(len(disc_iso)):

                    # -- Empty value
                    if disc_iso[i] == ' ':
                        pass
                    else:
                        flex_iso.append(disc_iso[i])

                # -- Recording duration divided into intervals corresponding to flex sensor sampling rate
                time_iso = []
                increment = 0
                while increment <= buffer_size_seconds:
                    time_iso.append( increment )
                    increment = float('{:.5f}'.format(increment + 0.01)) 

                # -- Continuous dataset ready to plot
                df = pd.DataFrame({'Time (s)': time_iso, 'Angular Displacement (deg)': flex_iso,})

            # -- Data spreadsheet saved to multiple files
            else:
                df = pd.read_csv(path + fn + ' -- Flex Sensor .csv')

            plot_window = plt.get_current_fig_manager()
            plot_window.window.showMaximized()

            plt.axes()
            plt.title('Flex Sensor Output', loc='center', pad=16)

            plt.xlabel('Time (s)')
            plt.xlim([0,buffer_size_seconds])
            plt.ylabel('Angular Displacement (Degrees)')

            plt.plot(df['Time (s)'], df['Angular Displacement (deg)'], linewidth=0.6, color='r')
            plt.show()

    # -- Real-time plot button for all piezosensors
    frame_live.grid(row=3, column=1)
    test_sp_btn = Button(frame_live, text="Test All Piezosensors", command=real_time_plot_piezos, height=3, width=24)
    test_sp_btn.grid(column=5, row=0, sticky='W', pady=(3,15))

    # -- Real-time plot button for ECG electrodes and flex sensor
    test_ef_btn = Button(frame_live, text="Test Electrode/Flex Sensor", command=real_time_plot_flexode, height=3, width=24 )
    test_ef_btn.grid(column=5, row=1, sticky='W')

    # -- Simultaneous data acquisition scan button
    scan_btn = Button(frame_scan, text="Start Scan", command=pre_scan_check, height=4, width=12)
    scan_btn.grid(column=0, row=3, pady=20)

    # -- Post-scan open spreadsheet buttons
    frame_post_scan_header.grid(row=4, column=0, pady=20)
    header_lbl = Label(frame_post_scan_header, text="Post-Scan Options:", font=16)      
    header_lbl.grid(column=0, row=0)

    frame_open.grid(row=5, column=0, padx=(40,0))
    open_btn = Button(frame_open, text="Open Main Spreadsheet", command=open_central, height=2, width=35)
    open_btn.grid(column=0, row=0)

    open_piezo_btn = Button(frame_open, text="Open Chest Strap Piezo Spreadsheet", command=open_piezos, height=2, width=35)
    open_piezo_btn.grid(column=0, row=1, pady=15)

    open_electrode_btn = Button(frame_open, text="Open Carotid/Femoral Piezo Spreadsheet", command=open_carotid, height=2, width=35)
    open_electrode_btn.grid(column=0, row=2)

    open_flex_btn = Button(frame_open, text="Open Electrode Spreadsheet", command=open_electr, height=2, width=35)
    open_flex_btn.grid(column=0, row=3, pady=15)

    open_flex_btn = Button(frame_open, text="Open Flex Sensor Spreadsheet", command=open_flex, height=2, width=35)
    open_flex_btn.grid(column=0, row=4)

    # -- Post-scan plot data buttons
    frame_plot.grid(row=5, column=1, padx=15, pady=(10,0))
    plot_piezo_btn = Button(frame_plot, text="Plot Chest Strap Piezo Data", command=post_plot_piezo, height=2, width=30)
    plot_piezo_btn.grid(column=0, row=0)

    plot_carotid_btn = Button(frame_plot, text="Plot Carotid/Femoral Piezo Data", command=post_plot_carotid, height=2, width=30)
    plot_carotid_btn.grid(column=0, row=1, pady=20)

    plot_electrode_btn = Button(frame_plot, text="Plot Electrode Data", command=post_plot_electrode, height=2, width=30)
    plot_electrode_btn.grid(column=0, row=2)

    plot_flex_btn = Button(frame_plot, text="Plot Flex Sensor Data", command=post_plot_flex, height=2, width=30)
    plot_flex_btn.grid(column=0, row=3, pady=20)

    '''
    If program log on the right side of the window is necessary:

    frame_log_header.grid(row=0, column=2)
    log_lbl = Label(frame_log_header, text="Log: ", font=16)          
    log_lbl.grid(column=0, row=0, padx=30,pady=10)

    frame_log.grid(row=0, column=3,pady=(20,0))


    If GUI plot on the right side of the window is necessary:

    fig = plt.Figure(figsize=(6,2), dpi=100)
    fig, ax = plt.subplots(nrows=4, ncols=2, sharex=True)
    ax1, ax2, ax3, ax4,ax5, ax6, ax7, ax8 = ax.flatten()
    plt.tight_layout()
    bar = FigureCanvasTkAgg(fig, window)
    bar.get_tk_widget().grid(column=10, row=0, padx=(40,0), pady=(0,0))

    '''

    window.mainloop()