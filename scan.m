clc

%% User Input
disp(' ');
sex = input( "Enter the sex: ", "s" );
disp(' ');
age = input( "Enter the age (yrs): " );
disp(' ');
duration = input("Enter the recording duration (sec): ");
disp(' ');
scans = input("Enter the rate of signal acquisition (scans/sec): " );

%% USB-1608fs Plus DAQ Device Object Instantiation
d = daq("mcc");
addinput(d,"Board0","Ai0","Voltage");
addinput(d,"Board0","Ai1","Voltage");
addinput(d,"Board0","Ai2","Voltage");
addinput(d,"Board0","Ai3","Voltage");
addinput(d,"Board0","Ai4","Voltage");
addinput(d,"Board0","Ai5","Voltage");
d.Rate = scans; %per second

%% Arduino Due Object Instantiation
a = serialport('COM3', 115200);
configureTerminator(a,"CR/LF");
flush(a);
a.UserData = struct("Data",[],"Count",1);

%% Helper Variables
totalScans = scans * duration;
rows = totalScans + 1;
eachScan = inv(scans);

%% Create Tables for Sex, Age, Analog Inputs, Digital Inputs, Timestamps, and Time Delays
times = seconds(0:eachScan:duration);
analogData = zeros(rows,9);

analogData = [analogData, [sex; strings(rows-1, 1)], [age; strings(rows-1, 1)]];
analogData(:,2) = strings(rows,1); analogData(:,9) = strings(rows,1);

analogData = array2timetable( analogData, 'RowTimes', times );
digitalData = strings(rows,1);
delays = zeros(rows, 1);

%% Initialize Sensor Readings
for j=1:4
    readline(a);
    read(d,seconds(eachScan));
end

%% Calibration
for i=1:rows
    tic;
    digitalData(i,1) = readline(a);
    analogData(i,3:8) = read(d,seconds(eachScan));
    pause(eachScan);
    delays(i) = toc - eachScan;
end
delay = eachScan - (mean(delays, 'all'));


%% Synchronized Data Acquisition
if eachScan <= (mean(delays, 'all')) 
    tic;
    for i=1:rows

        digitalData(i,1) = readline(a);
        analogData(i,3:8) = read(d,seconds(eachScan));
    end
    toc;
else 
    tic;
    for i=1:rows
        digitalData(i,1) = readline(a);
        analogData(i,3:8) = read(d,seconds(eachScan));
        pause(delay)
    end
    toc;
end

%% Merge into Single Table
digitalData = table(str2double(digitalData));
analogData(:,1) = digitalData;

analogData.Properties.VariableNames = {'Angular Displacement (Degrees)', ... 
                                       '  ', 'Ch0', 'Ch1', 'Ch2', 'Ch3', ... 
                                       'Ch4', 'Ch5', ' ', 'Sex', 'Age' };

%% Save as .CSV
[FileName, PathName] = uiputfile('*.csv', 'Save table as:');
if ischar(FileName)
    File = fullfile(PathName, FileName);
    try 
        writetimetable(analogData, File);
    catch
        warning('File to edit is open and running. Please close the file.');
    end
else
    disp('')
    disp('User aborted the dialog. Data not saved to spreadsheet.')
end

%% Plot Analog/Digital Data
valid = false;
while valid == false
    disp(" ")
    whichPlot = input( "Open Spreadsheet (0) - Plot analog data (1) - Plot digital data (2) - Exit (3) --- " );
    switch whichPlot
        case 0
            winopen(FileName)
            pause(1)
        case 1
            analogOnly = [analogData.Ch0, analogData.Ch1, analogData.Ch2, ...
                          analogData.Ch3, analogData.Ch4, analogData.Ch5];
            plot(analogData.Time, str2double(analogOnly));
            xlabel("Time")
            ylabel("Amplitude (V)")
            legend("Ch0", "Ch1", "Ch2", "Ch3", "Ch4", "Ch5")
            pause(1)
        case 2
            plot(analogData.Time, table2array(digitalData))
            xlabel("Time")
            ylabel("Angular Displacement (Degrees)")
            pause(1)
        case 3
            valid = true;
        otherwise
            disp("Please enter a valid entry");
    end
end

%% End Program
delete(a);
delete(d);
disp(' ');
disp("Scan Completed.");
pause(2);
clear
clc