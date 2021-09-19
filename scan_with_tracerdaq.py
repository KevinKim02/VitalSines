'''
    Pairable Windows program capable of running simultaneously with the external data acquisition software TracerDAQ (or TracerDAQ Pro).
    TracerDAQ softwares allow for simultaneous data acquisition, data analysis, real-time display, and signal generation from DAQ devices such as the USB-1608fs-Plus.
    This program offers time-synchronized reading from the serial port at 100Hz, data compliation into one spreadsheet, post-scan data plotting and analysis.
    Program detects specific key clicks which correspond to events such as the start of the scan and when the data file is saved on the external software.
    (see the user manual in the repository for steps on concurrent usage with TracerDAQ)

    Hardware Setup at the Time of Program Development:
     - 6 custom piezoelectric sensors connected to 6 analog input channels of a USB-1608fs-Plus device
     - 2 HK-2000B piezoelectric sensors connected to 2 analog input channels of another USB-1608fs-Plus device
     - 1 Bend Labs digital one-axis flex sensor connected to an Arduino Due
     - USB hub for combining connections from Arduino Due and 2 USB-1608fs-Plus devices to 1 USB input into the Windows PC

    Software Setup at the Time of Program Development:
    - Uploaded bend_polled_demo.ino to the Arduino Due using Arduino IDE v1.8.15 for flex sensor configuration prior to scanning 
      (see bend_polled_demo folder in the repository for the uploaded code and dependencies)
    - InstaCal downloaded for USB-1608fs-Plus device configuration (https://www.mccdaq.com/daq-software/instacal.aspx)
    - TracerDAQ or TracerDAQ Pro downloaded (https://www.mccdaq.com/daq-software/tracerdaq-series.aspx)
      
    - Installed Software:
        Python 3.9.2
        pip 21.1.3
        keyboard 0.13.5
        matplotlib 3.4.2
        numpy 1.21.0
        pandas 1.2.4
        pyserial 3.5

'''
from tkinter import *
from multiprocessing import Process, Queue
from time import time, sleep ,strftime, localtime
from datetime import datetime, date
import keyboard, win32api, serial, os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.backend_bases import key_press_handler

# -- Central File Name
fn = ''

# -- tkinter GUI Window
def gui_start(q, status):

    # -- tkinter Window Settings
    window = Tk()
    window.title("Enter Fields")
    window.geometry('890x50') 

    # -- Patient Initial Field
    initial_lbl = Label(window, text="Initials: ")
    initial_lbl.grid(column=0, row=0, padx=(15,2), pady=15)
    initial_entry = Entry(window ,width=10)
    initial_entry.grid(column=1, row=0,padx=(2,15), pady=15)

    # -- Patient Date of Birth Field
    dob_lbl = Label(window, text="Date of Birth (MM-DD-YYYY): ")
    dob_lbl.grid(column=2, row=0, padx=(15,2), pady=15)
    dob_entry = Entry(window,width=15)
    dob_entry.grid(column=3, row=0,padx=(2,15), pady=15)

    # -- Patient Sex Field
    sex_lbl = Label(window, text="Sex: ")
    sex_lbl.grid(column=4, row=0, padx=(20,15), pady=15)
    sex_entry = StringVar(value='M')
    Radiobutton(window, text='Male',variable=sex_entry, value='M').grid(column=5, row=0, sticky='W', pady=15)
    Radiobutton(window, text='Female',variable=sex_entry, value='F').grid(column=6, row=0, sticky='W', pady=15)

    # -- Acquire User Input from GUI Fields
    def get_all():

        # -- Clear Queue Before Each Scan
        if not q.empty():
            while not q.empty():
                q.get()

        q.put(str(initial_entry.get()))
        q.put(str(dob_entry.get()))
        q.put(str(sex_entry.get()))

        initial_entry.delete(0, 'end')
        dob_entry.delete(0, 'end')

        if not status.empty():
            while not status.empty():
                status.get()
        status.put(False)

    # -- Post-Scan Plot Function
    def plot_data():

        # -- Handle Button Clicks Before Completion of First Scan
        if status.empty():
            pass
        else:
            state = status.get()

            # -- Allow Plotting
            if state:
                fn = q.get()

                # -- Allow for Plotting Again After Window is Closed
                status.put(True)
                q.put(fn)

                # -- Extract Main Data
                df = pd.read_csv(fn, skiprows=8, sep=',', names=[ 'Date/Time', 'Carotid Piezo (V)', 'Femoral Piezo (V)', 'Acoustic Piezo (V)', 'Chest Strap Channel 1 Piezo (V)', 'Chest Strap Channel 2 Piezo (V)','Chest Strap Channel 3 Piezo (V)', 'Chest Strap Channel 4 Piezo (V)', 'Chest Strap Channel 5 Piezo (V)', 'Electrodes (V)', 'Angular Displacement (deg)'])
                
                t = pd.DataFrame(np.arange(0, 60, 0.001).tolist(), columns=['Time (s)'])
                t.index += 1

                # -- Extract Flex Sensor Data 
                fdf = (df['Angular Displacement (deg)']).dropna()
                fdf = fdf.reset_index(drop=True)
                fdf.index = fdf.index + 1

                ft = pd.DataFrame(np.arange(0, 60, 0.01).tolist(), columns=['Time (s)'])
                ft.index += 1

                # -- Create Main Figure
                def config_plot():
                    fig, ax = plt.subplots(figsize=(10,7))
                    fig.tight_layout()
                    return (fig, ax)

                # -- tkinter Plot GUI Settings
                class main_plot:
                    def __init__(self, master):
                        self.master = master
                        self.frame = Frame(self.master)
                        self.fig, self.ax = config_plot()

                        self.canvas = FigureCanvasTkAgg(self.fig, self.master)  
                        self.config_window()
                        self.frame.pack(expand=YES, fill=BOTH)

                    def config_window(self):
                        self.canvas.mpl_connect("key_press_event", self.on_key_press)
                        self.toolbar = NavigationToolbar2Tk(self.canvas, self.master)
                        self.toolbar.update()
                        self.canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)

                        # -- GUI Buttons
                        self.quit_btn = Button(self.master, text="Quit", command=self._quit, height=4, width=15)
                        self.quit_btn.pack(side=RIGHT, padx=(0,30))

                        self.carotid_btn = Button(self.master, text="Carotid", command=self.plot_carotid, height=4, width=12)
                        self.carotid_btn.pack(side=LEFT, padx=(40,22))

                        self.femoral_btn = Button(self.master, text="Femoral", command=self.plot_femoral, height=4, width=12)
                        self.femoral_btn.pack(side=LEFT, padx=22)

                        self.acoustic_btn = Button(self.master, text="Acoustic", command=self.plot_acoustic, height=4, width=12)
                        self.acoustic_btn.pack(side=LEFT, padx=22)

                        self.ch1_btn = Button(self.master, text="Chest Strap 1", command=self.plot_ch1, height=4, width=12)
                        self.ch1_btn.pack(side=LEFT, padx=22)

                        self.ch2_btn = Button(self.master, text="Chest Strap 2", command=self.plot_ch2, height=4, width=12)
                        self.ch2_btn.pack(side=LEFT, padx=22)

                        self.ch3_btn = Button(self.master, text="Chest Strap 3", command=self.plot_ch3, height=4, width=12)
                        self.ch3_btn.pack(side=LEFT, padx=22)

                        self.ch4_btn = Button(self.master, text="Chest Strap 4", command=self.plot_ch4, height=4, width=12)
                        self.ch4_btn.pack(side=LEFT, padx=22)

                        self.ch5_btn = Button(self.master, text="Chest Strap 5", command=self.plot_ch5, height=4, width=12)
                        self.ch5_btn.pack(side=LEFT, padx=22)

                        self.electrode_btn = Button(self.master, text="Electrode", command=self.plot_electrode, height=4, width=12)
                        self.electrode_btn.pack(side=LEFT, padx=22)

                        self.flex_sensor_btn = Button(self.master, text="Flex Sensor", command=self.plot_flex, height=4, width=12)
                        self.flex_sensor_btn.pack(side=LEFT, padx=22)

                    # -- Functions for Clearing and Plotting Data
                    def plot_carotid(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Carotid Piezo (V)'], linewidth=0.6, color='r')
                        self.ax.set(title='Carotid Artery Piezosensor', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(-3,3))
                        self.canvas.draw()

                    def plot_femoral(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Femoral Piezo (V)'], linewidth=0.6, color='g')
                        self.ax.set(title='Femoral Artery Piezosensor', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(-3,3))
                        self.canvas.draw()

                    def plot_acoustic(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Acoustic Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Acoustic Piezosensor', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_ch1(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Chest Strap Channel 1 Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Chest Strap Piezosensor (Channel 1)', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_ch2(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Chest Strap Channel 2 Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Chest Strap Piezosensor (Channel 2)', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_ch3(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Chest Strap Channel 3 Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Chest Strap Piezosensor (Channel 3)', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_ch4(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Chest Strap Channel 4 Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Chest Strap Piezosensor (Channel 4)', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_ch5(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Chest Strap Channel 5 Piezo (V)'], linewidth=0.6, color='b')
                        self.ax.set(title='Chest Strap Piezosensor (Channel 5)', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(3,7))
                        self.canvas.draw()

                    def plot_electrode(self):
                        self.ax.clear()
                        self.ax.plot(t['Time (s)'], df['Electrodes (V)'], linewidth=0.6, color='m')
                        self.ax.set(title='Electrode', xlabel='Time (s)', ylabel='Amplitude (V)', xlim=(0,60), ylim=(0,6))
                        self.canvas.draw()

                    def plot_flex(self):
                        self.ax.clear()
                        self.ax.plot(ft['Time (s)'], fdf, linewidth=0.6, color='m')
                        self.ax.set(title='Flex Sensor', xlabel='Time (s)', ylabel='Angular Displacement (deg)', xlim=(0,60), ylim=(-20,20))
                        self.canvas.draw()

                    def on_key_press(self, event):
                        key_press_handler(event, self.canvas, self.toolbar)

                    # -- Close Plot Window
                    def _quit(self):
                        self.master.destroy()
                
                root = Tk()
                root.attributes('-fullscreen', True)
                main_plot(root)
                root.mainloop()

            # -- Prevent Plotting When Scan is Incomplete
            else: 
                status.put(False)
    
    # -- Enqueue User Inputs and Clear Fields
    btn = Button(window, text="Save Fields", command=get_all, height=1, width=10)
    btn.grid(column=7, row=0, padx=(50,20), pady=15)

    # -- Plots Data Only After Scan is Completed
    plot = Button(window, text="Plot Data", command=plot_data, height=1, width=10)
    plot.grid(column=8, row=0, padx=(10,20), pady=15)

    window.mainloop()

# -- Simultaneous Scan Function
def save(q,status):

    global alt_df, fn_time, te

    # -- DataFrame for Flex Sensor Daa
    alt_df = ''

    # -- Start Time of Scan
    fn_time = ''

    # -- End Time of Scan
    te = ''

    # -- Forever Loop Running the Program
    not_done = True
    while not_done: 

        # -- Detect Request for Scan (Hold s + Left Click)
        if keyboard.is_pressed('s') and win32api.GetKeyState(0x01) < 0: 

            # -- Connect to Serial Port (Change Serial Port Name and Baud Rate)
            ser = serial.Serial('COM3', 115200, timeout=None)
            ser.flushInput()

            # Initialize Flex Sensor
            temp_scan = ""
            while temp_scan != "One Axis ADS initialization succeeded...":
                temp_scan = ser.readline()
                try:
                    temp_scan = temp_scan.decode("utf-8")
                    temp_scan = temp_scan[:-2]
                except UnicodeDecodeError:
                    pass
            print('Flex Sensor Connected')

            digital_data = []
            te = time() + 60
            print('Start ---  ', time())

            # -- Flex Sensor Scan Starts
            while time() <= te:
                digital_data.append(ser.readline().decode('utf-8').strip())
            print('End ---  ', time())


            # -- Close Serial Port Connection
            ser.close()

            print(len(digital_data))
            if len(digital_data) == 6001:
                del digital_data[0]

            elif len(digital_data) == 6002:
                del digital_data[0]
                del digital_data[0]
            
            elif len(digital_data) == 6003:
                del digital_data[0]
                del digital_data[0]
                del digital_data[-1]

            elif len(digital_data) == 6004:
                del digital_data[0]
                del digital_data[0]
                del digital_data[-1]
                del digital_data[-1]

            # -- Discrete Index Column for Joining with Main DataFrame
            join = []
            df_index = 1
            for i in range(1,6001):
                join.append(df_index)
                df_index += 10

            alt_df = pd.DataFrame(digital_data, join, columns=['Angular Displacement (deg)'])
            fn_time = strftime('%H;%M;%S', localtime(te-60))

        # -- Detect Request for Save (Click Enter for Saving File Named '1.csv')
        if keyboard.is_pressed('enter'):
            sleep(2)

            # -- Main DataFrame for Carotid, Femoral, Acoustic, and 5 Chest Strap Piezosensor Data
            main_df = pd.read_csv('1.csv', skiprows=8, sep=',', names=[ 'Date/Time', 'Carotid Piezo (V)', 'Femoral Piezo (V)', 'Acoustic Piezo (V)', 
                                                                        'Chest Strap Channel 1 Piezo (V)', 'Chest Strap Channel 2 Piezo (V)','Chest Strap Channel 3 Piezo (V)', 
                                                                        'Chest Strap Channel 4 Piezo (V)', 'Chest Strap Channel 5 Piezo (V)', 'Electrodes (V)', 'Events', ' '])
            main_df.drop(axis=1, labels=['Events', ' '], inplace=True )
            print(main_df)
            # -- Dequeue User Fields (Queue Size = 3)

            # -- Patient Initials
            tmp0 = q.get()

            # -- Patient Date of Birth
            tmp1 = q.get()

            # -- Patient Sex
            tmp2 = q.get()

            fn = fn_time + ' -- ' + tmp0 + ' -- ' +  tmp1 + ' -- ' +  tmp2 + ' .csv'

            # -- Enqueue Central File Name (Queue Size = 1)
            q.put(fn)

            # -- Patient Age Calculation
            birthday = datetime.strptime(tmp1, "%m-%d-%Y")
            today = date.today()
            age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
            
            if tmp2 == 'M':
                sex = 'Male'
            else:
                sex = 'Female'

            # -- Edit Default Information Headers
            separate_rows = pd.read_csv('1.csv',  nrows=7, names=['Info'])
            separate_rows.iloc[0][0] = 'Initials: ' + tmp0
            separate_rows.iloc[1][0] = 'Sex: ' + sex
            separate_rows.iloc[2][0] = 'Age: ' + str(age)
            separate_rows.iloc[3][0] = 'Date of Birth: ' + birthday.strftime("%b %d, %Y")
            separate_rows.iloc[4][0] = 'Sampling Interval: 0.001 (All Piezosensors, Electrodes), 0.01 (Flex Sensor)'
            separate_rows.iloc[5][0] = 'Sampling Rate: 1000 (All Piezosensors, Electrodes), 100 (Flex Sensor)'
            separate_rows.iloc[6][0] = 'Sample Count: 60000 (All Piezosensors, Electrodes), 6000 (Flex Sensor)'
            
            # -- Time Synchronization for Main Read and Flex Sensor Read
            replace = datetime.fromtimestamp(te-60).strftime('%m/%d/%Y %I:%M:%S.%f')[:-3] + datetime.fromtimestamp(te-60).strftime(' %p')

            not_found = True
            j = 1

            # -- Linear Row Iteration through Main DataFrame to Drop First Few Rows Until the Start of Flex Sensor Read
            while not_found:
                # -- Time of Synchronization Detected
                if main_df.iloc[j][0] == replace:

                    # -- Drop Excess Head Data
                    to_drop1 = list(range(1,j))
                    main_df = main_df.drop(to_drop1, axis=0)
                    main_df = main_df.reset_index(drop=True)
                    main_df.index = main_df.index + 1

                    # -- Drop Excess Tail Data
                    to_drop2 = list(range(60001, len(main_df)+1))
                    main_df = main_df.drop(to_drop2, axis=0)
                    not_found = False

                j += 1

            # -- Main DataFrame and Flex Sensor DataFrame Concatenation by Index Column
            df = pd.concat([main_df,alt_df], axis=1).fillna('')
        
            # -- Update Temporary File Name to Central File Name
            os.rename('1.csv', fn)

            # -- Include Information Headers
            with open(fn, 'wb') as csvfile:
                separate_rows.to_csv(csvfile, index=False, header=False)
                df.to_csv(csvfile, index=True, header=True)

            if not status.empty():
                while not status.empty():
                    status.get()

            # -- Scan Status: Complete, Allow Plotting
            status.put(True)

        # End Program (Click Esc)
        if keyboard.is_pressed('esc'):
            not_done = False

if __name__ == '__main__':
    # -- Instantiate Queue to Share Data Between Processes
    q = Queue()

    # -- Instantiate Queue to Share Scan Status Between Processes
    status = Queue()
    
    # -- Initiate Simultaneous Processes
    Process(target=gui_start, args=(q,status)).start()
    Process(target=save, args=(q,status)).start()