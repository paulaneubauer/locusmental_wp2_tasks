"""
Go-NoGo Task
- Baseline: 5 s fixation cross (gaze-contingent)
- Stimulus: 1200 ms (go image or nogo image, gaze-contingent)
- ISI: 300–800 ms fixation cross (gaze-contingent)
- Conditions: go (60%), nogo_dominant (20%), nogo_rare1 (10%), nogo_rare2 (10%)
- Hit = go trial with response, Miss = go trial without response
- Correct rejection = nogo trial without response, False alarm = nogo trial with response
- Practice block: 3 phases (go-only → mostly go → mixed), with performance criterion (65%)
  and up to 2 repeats of phases 2+3 if criterion not met; feedback shown after each practice trial
- Main block: 200 trials, 2-minute break at trial 100
- Uses mouse as fake eye-tracker (move mouse cursor to simulate gaze) when testmode is True
"""

# ================================
# IMPORTS
# ================================
from psychopy import visual, core, event, clock, data, gui, monitors
import random, time, numpy
# For controlling eye tracker and eye-tracking SDK:
import tobii_research as tr
from psychopy.iohub import launchHubServer
# For getting keyboard input:
from psychopy.hardware import keyboard
from psychopy.monitors import Monitor
# For managing paths:
from pathlib import Path
# For logging data in a .log file:
import logging
from datetime import datetime
import json
import sys

#send trigger via LSL
from pylsl import StreamInfo, StreamOutlet

# Suppress pygame and LSL messages 
import os # 
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ["LSL_LOG_LEVEL"] = "fatal" # removes messages in CMD

# LOAD CONFIG
with open("tasks/config.json", "r") as file: 
    config = json.load(file)

# Select the task 
task_name = "go_nogo"
if task_name not in config["tasks"]:
    raise KeyError(f"Task '{task_name}' not found in config.json")

task_config = config["tasks"][task_name]
constants = config["constants"]

# SETUP
# # setup logging - will be written to a file (data/logging_data):
current_datetime = datetime.now()
formatted_datetime = str(current_datetime.strftime("%Y-%m-%d %H-%M-%S"))
logging_path =  Path(task_config["logging"]["base_path"], task_config["logging"]["log_folder"]).resolve()
filename_gonogo_task = os.path.join(logging_path, formatted_datetime)

# Check if the directory exists
if not logging_path.exists():
    # If it doesn't exist, create it
    logging_path.mkdir(parents=True, exist_ok=True)
else:
    print(f"Directory {logging_path} already exists. Continuing to use it.")

logging.basicConfig(
    level = logging.DEBUG,
    filename = filename_gonogo_task,
    filemode = 'w', # w = write, for each subject an separate log file.
    format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s')

trials_data_folder = Path(task_config["data_paths"]["trials"]).resolve()
eyetracking_data_folder = Path(task_config["data_paths"]["eyetracking"]).resolve()

if not trials_data_folder.exists():
    trials_data_folder.mkdir(parents=True)
    
if not eyetracking_data_folder.exists():
    eyetracking_data_folder.mkdir(parents=True)

print(f"THIS IS {task_name.upper()}")
logging.info(f"THIS IS {task_name.upper()}")

# testmode options
# testmode_et = TRUE mimics an eye-tracker by mouse movement, FALSE = eye-tracking hardware is required and adressed with tobii_research module
testmode_et = config["constants"]["eyetracker"]["testmode"]
sampling_rate = config["constants"]["eyetracker"]["sampling_rate"] # Tobii Pro Spark = 60Hz, Tobii Pro Spectrum = 300Hz, Tobii TX-300 (ATFZ) = 300 Hz
background_color_rgb = config["constants"]["psychopy_window"]["background_color"]
size_fixation_cross_in_pixels = config["constants"]["psychopy_window"]["size_fixation_cross_in_pixels"]

# Create the LSL Stream
# 3-channel string markers 
info = StreamInfo(
    name='Markers',           # Stream name (must match what you select in LabRecorder)
    type='Markers',           # Stream type (must match in LabRecorder)
    channel_count=3,          # 1 for simple triggers
    nominal_srate=0,          # Irregular sampling rate for event markers
    channel_format='string',  # Markers are usually strings
    source_id='stimulus_stream'  # Unique ID for your experiment/session
)
outlet = StreamOutlet(info)

# CONSTANTS AND STIMULI
# Experimental settings:
# Input dialogue boxes are presented on external screen 0.
dialog_screen = config["constants"]["dialog_screen"]
# Stimuli are presented on internal screen 1.
presentation_screen =  config["constants"]["presentation_screen"]
current_screen = presentation_screen  # Start in presentation mode

stimulus_duration_in_seconds = 1.2
# Inter Stimulus Interval (ISI) randomly varies between value0 and value1.
ISI_interval = [300, 800]
# Sensitivity: Warning of gaze offset from the center.
gaze_offset_cutoff = 3 * size_fixation_cross_in_pixels
# Presentation duration of baseline screen, in seconds.
baseline_duration = 5
# After 500 ms the no_data detection warning should be displayed on the screen.no_data_warning_cutoff = 0.5
no_data_warning_cutoff = 0.5
# Settings are stored automatically for each trial.
settings = {}

GO_KEY = task_config["response"]["key_go"]
print(f"GO_KEY for this task: {GO_KEY}")

# Presenting a dialog box. Infos are added to settings.
# settings['id'] = 123 #default testing value
# Create a dialog box for participant info
# Get participant ID and timepoint from command-line arguments
# Participant/timepoint from CLI or dialog fallback:
try:
    participant_id = sys.argv[1]
    timepoint = sys.argv[2]
    cap_size = sys.argv[3]
except Exception:
    dlg = gui.Dlg(title="Participant info")
    dlg.addField("participant_id:")
    dlg.addField("timepoint:")
    dlg.addField("cap_size_cm:")
    ok_data = dlg.show()
    if dlg.OK:
        participant_id = ok_data[0]
        timepoint = ok_data[1]
        cap_size = ok_data[2]
    else:
        raise RuntimeError("No participant ID provided — aborting.")

selected_timepoint = timepoint

# Name for output data:
# participant_id and selected_timepoint come from the dialog box input
fileName = f'{task_name}_{participant_id}_{selected_timepoint}_{data.getDateStr(format="%Y-%m-%d-%H%M")}'

settings['cap_size_cm'] = cap_size

# Experiment handler saves experiment data automatically.
# The dictionary "settings" is passed to the experiment handler.
exp = data.ExperimentHandler(
    name=task_name,
    version='0.4', # updated version for 4-stimulus design
    extraInfo = settings,
    dataFileName = str(trials_data_folder / fileName),
    )

# Monitor and Window
MONITOR_NAME = config["constants"]["monitor"]["name"]

mon = Monitor(MONITOR_NAME)
mon.setWidth(config["constants"]["monitor"]["width_cm"])  # Physical width of the screen
mon.setDistance(config["constants"]["monitor"]["distance_cm"])  # Distance from participant
mon.setSizePix([config["constants"]["monitor"]["width"], config["constants"]["monitor"]["height"]])  # Screen resolution

mywin = visual.Window(
    size=(config["constants"]["monitor"]["width"], config["constants"]["monitor"]["height"]),
    fullscr=config["constants"]["psychopy_window"]["fullscreen"],
    screen=config["constants"]["presentation_screen"],
    color=config["constants"]["psychopy_window"]["background_color"],
    monitor=MONITOR_NAME,
    units='pix'
)

refresh_rate = mywin.monitorFramePeriod #get monitor refresh rate in seconds
print('monitor refresh rate: ' + str(round(refresh_rate, 3)) + ' seconds')

# ================================
# STIMULI
# ================================
base_path = Path(config["task_base_path"]).resolve()
# folder dedicated for Go/NoGo images
media_folder = base_path / config["media"]["go_nogo"]

# --- Image paths ---
# go (60%): apple
go_image_path      = media_folder / "SHINE_color_cielab_1_isoluminant.png"
# nogo_dominant (20%): fruit 1
nogo_dom_image_path  = media_folder / "SHINE_color_cielab_5_isoluminant.png"
# nogo_rare1 (10%): fruit 2
nogo_rare1_image_path = media_folder / "SHINE_color_cielab_4_isoluminant.png"
# nogo_rare2 (10%): fruit 3
nogo_rare2_image_path = media_folder / "SHINE_color_cielab_6_isoluminant.png"

for p in [go_image_path, nogo_dom_image_path, nogo_rare1_image_path, nogo_rare2_image_path]:
    if not p.exists():
        raise FileNotFoundError(f"Stimulus image not found: {p}")

# Stimulus size
original_size = (197, 281)  
scale_factor = 2
stimulus_size = (
    original_size[0] * scale_factor,
    original_size[1] * scale_factor
)

go_stimulus = visual.ImageStim(
    win=mywin,
    image=str(go_image_path),
    size=stimulus_size,
    pos=(0, 0)
)

nogo_dom_stimulus = visual.ImageStim(
    win=mywin,
    image=str(nogo_dom_image_path),
    size=stimulus_size,
    pos=(0, 0)
)

nogo_rare1_stimulus = visual.ImageStim(
    win=mywin,
    image=str(nogo_rare1_image_path),
    size=stimulus_size,
    pos=(0, 0)
)

nogo_rare2_stimulus = visual.ImageStim(
    win=mywin,
    image=str(nogo_rare2_image_path),
    size=stimulus_size,
    pos=(0, 0)
)

# Map trial_type strings to ImageStim objects for clean lookup in present_stimulus()
STIMULUS_MAP = {
    'go':         go_stimulus,
    'nogo_dom':   nogo_dom_stimulus,
    'nogo_rare1': nogo_rare1_stimulus,
    'nogo_rare2': nogo_rare2_stimulus,
}

# Create feedback stimuli (robust Unicode)
correct_feedback = visual.TextStim(
    win=mywin,
    text='☺',          # or ':)'
    pos=(0, 0),
    height=400,
    color=(0, 131, 0)
)

incorrect_feedback = visual.TextStim(
    win=mywin,
    text='☹',          # or ':('
    pos=(0, 0),
    height=400,
    color=(255, 0, 0)
)

# EYE TRACKING SETUP
#Setup Eye Tracking:
if testmode_et:
    logging.info('TESTMODE = TRUE')
    print('Mouse is used to mimic eye tracker...')
    iohub_config = {
        'eyetracker.hw.mouse.EyeTracker': {'name': 'tracker'}
    }
else:
    logging.info('TESTMODE = FALSE')
    
    # Search for eye trackers:
    found_eyetrackers = tr.find_all_eyetrackers()
    if not found_eyetrackers:
        raise RuntimeError("No eye tracker found. Please check the connection.")
    
    # Select the first available eye tracker:
    my_eyetracker = found_eyetrackers[0]
    sampling_rate = my_eyetracker.get_all_gaze_output_frequencies()[0]
    
    # Log eye tracker details:
    print(f"Tracker connected:\n"
          f"Address: {my_eyetracker.address}\n"
          f"Model: {my_eyetracker.model}\n"
          f"Sampling Rates: {my_eyetracker.get_all_gaze_output_frequencies()}")
    logging.info(f"ADDRESS: {my_eyetracker.address}")
    logging.info(f"MODEL: {my_eyetracker.model}")
    logging.info(f"SERIAL NUMBER: {my_eyetracker.serial_number}")

    # Define ioHub configuration:
    iohub_config = {
        'eyetracker.hw.tobii.EyeTracker': {
            'name': 'tracker',
            'runtime_settings': {'sampling_rate': sampling_rate}
        }
    }

# Launch ioHub server:
io = launchHubServer(
    **iohub_config,
    experiment_code=str(eyetracking_data_folder),
    session_code=fileName,
    datastore_name=str(eyetracking_data_folder / fileName),
    window=mywin
)

# Initialize tracker
tracker = io.devices.tracker
if not tracker:
    raise RuntimeError("Tracker initialization failed. Please check your eye tracker configuration.")

# Start eye tracker recording
print("Tracker successfully initialized!")
tracker.setRecordingState(True)

# SETUP KEYBORD
kb = keyboard.Keyboard()

# HELPER FUNCTIONS
# feedback function
def show_practice_feedback(accuracy):
    if accuracy in ['hit', 'correct_rejection']:
        correct_feedback.draw()
    else:
        incorrect_feedback.draw()

    mywin.flip()
    core.wait(PRACTICE_FEEDBACK_DURATION)

# AREA OF INTEREST (AOI)
AOI_MARGIN_PX = size_fixation_cross_in_pixels * 1.5

AOI_HALF_WIDTH = (stimulus_size[0] / 2) + AOI_MARGIN_PX
AOI_HALF_HEIGHT = (stimulus_size[1] / 2) + AOI_MARGIN_PX

# create Areas of Interest
def gaze_on_stimulus(gaze):
    if gaze is None:
        return False

    x, y = gaze

    return (
        -AOI_HALF_WIDTH <= x <= AOI_HALF_WIDTH and
        -AOI_HALF_HEIGHT <= y <= AOI_HALF_HEIGHT
    )

#Send a trigger (marker) function
def send_trigger(marker):
    # marker must be a list of strings, length = channel_count
    outlet.push_sample(marker)

# Random interstimulus interval (SI):
def define_ISI_interval():
    ISI = random.randint(ISI_interval[0], ISI_interval[1])
    ISI = ISI/1000 #get to second format
    return ISI

# Draw a fixation cross from lines:
def draw_fixcross(background_color=background_color_rgb, cross_color='black', gaze_overlay=False):
    # Draw background if different from default
    if background_color is not background_color_rgb:
        background_rect = visual.Rect(win=mywin, size=mywin.size, fillColor=background_color)
        background_rect.draw()

    # Draw cross lines
    line1 = visual.Line(win=mywin, units='pix', lineColor=cross_color)
    line1.start = [-(size_fixation_cross_in_pixels/2), 0]
    line1.end = [+(size_fixation_cross_in_pixels/2), 0]

    line2 = visual.Line(win=mywin, units='pix', lineColor=cross_color)
    line2.start = [0, -(size_fixation_cross_in_pixels/2)]
    line2.end = [0, +(size_fixation_cross_in_pixels/2)]

    line1.draw()
    line2.draw()

# Draw figure when gaze is offset for gaze contigency:
def draw_gazedirect(background_color=background_color_rgb):
    if background_color is not background_color_rgb:
        background_rect = visual.Rect(
            win = mywin,
            size = mywin.size,
            fillColor = None)
        background_rect.draw()
    function_color = 'red'
    arrow_size_pix = size_fixation_cross_in_pixels
    arrow_pos_offset = 5
    width = 3

    rect1 = visual.Rect(
        win = mywin,
        units = 'pix',
        lineColor = function_color,
        fillColor = None, # outline only so that stimulus is still visible when drawn
        lineWidth = width,
        size = size_fixation_cross_in_pixels*6)

    # Arrow left:
    al_line1 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    al_line1.start = [-(arrow_size_pix*arrow_pos_offset), 0]
    al_line1.end = [-(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]
    al_line2 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    al_line2.start = [-(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2)), -arrow_size_pix/2]
    al_line2.end = [-(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]
    al_line3 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    al_line3.start = [-(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2)), +arrow_size_pix/2]
    al_line3.end = [-(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]

    # Arrow right:
    ar_line1 = visual.Line(win = mywin, units='pix', lineColor = function_color, lineWidth = width)
    ar_line1.start = [+(arrow_size_pix*arrow_pos_offset), 0]
    ar_line1.end = [+(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]
    ar_line2 = visual.Line(win = mywin, units='pix', lineColor = function_color, lineWidth = width)
    ar_line2.start = [+(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2)), -arrow_size_pix/2]
    ar_line2.end = [+(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]
    ar_line3 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    ar_line3.start = [+(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2)), +arrow_size_pix/2]
    ar_line3.end = [+(arrow_size_pix*arrow_pos_offset-arrow_size_pix), 0]

    # Arrow top:
    at_line1 = visual.Line(win = mywin, units='pix', lineColor = function_color, lineWidth = width)
    at_line1.start = [0, +(arrow_size_pix*arrow_pos_offset)]
    at_line1.end = [0, +(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]
    at_line2 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    at_line2.start = [-arrow_size_pix/2, +(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2))]
    at_line2.end = [0, +(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]
    at_line3 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    at_line3.start = [+arrow_size_pix/2, +(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2))]
    at_line3.end = [0, +(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]

    # Arrow bottom:
    ab_line1 = visual.Line(win = mywin, units='pix', lineColor = function_color, lineWidth = width)
    ab_line1.start = [0, -(arrow_size_pix*arrow_pos_offset)]
    ab_line1.end = [0, -(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]
    ab_line2 = visual.Line(win = mywin, units = 'pix', lineColor = function_color, lineWidth = width)
    ab_line2.start = [+arrow_size_pix/2, -(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2))]
    ab_line2.end = [0, -(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]
    ab_line3 = visual.Line(win = mywin, units='pix', lineColor = function_color, lineWidth = width)
    ab_line3.start = [-arrow_size_pix/2, -(arrow_size_pix*arrow_pos_offset-(arrow_size_pix/2))]
    ab_line3.end = [0, -(arrow_size_pix*arrow_pos_offset-arrow_size_pix)]

    #draw all
    al_line1.draw()
    al_line2.draw()
    al_line3.draw()

    ar_line1.draw()
    ar_line2.draw()
    ar_line3.draw()

    at_line1.draw()
    at_line2.draw()
    at_line3.draw()

    ab_line1.draw()
    ab_line2.draw()
    ab_line3.draw()

    rect1.draw()

# Check for keypresses, used to pause and quit experiment:
def check_keypress():
    global current_screen
    keys = kb.getKeys(['p','escape'], waitRelease = True)
    timestamp_keypress = clock.getTime()

    # Extract key names from the KeyPress objects and print them
    key_names = [key.name for key in keys]

    if any(key.name == 'escape' for key in keys):
        dlg = gui.Dlg(title='Quit?', labelButtonOK=' OK ', labelButtonCancel=' Cancel ')
        dlg.addText('Do you really want to quit? - Then press OK')
        dlg.screen = dialog_screen
        dlg.show()  # show dialog and wait for OK or Cancel
        if dlg.OK:  # or if ok_data is not None
            print('EXPERIMENT ABORTED!')
            core.quit()
        else:
            print('Experiment continues...')
            current_screen = presentation_screen
        pause_time = clock.getTime() - timestamp_keypress

    elif any(key.name == 'p' for key in keys):
        dlg = gui.Dlg(title='Pause', labelButtonOK='Continue')
        dlg.addText('Experiment is paused - Press Continue, when ready')
        dlg.screen = dialog_screen
        dlg.show()  # show dialog and wait for OK
        pause_time = clock.getTime() - timestamp_keypress
    else:
        pause_time = 0
        # Show the experiment window again
        current_screen = presentation_screen
    pause_time = round(pause_time,3)
    return pause_time

def check_nodata(gaze_position):
    if gaze_position == None:
        nodata_boolean = True
    else:
        nodata_boolean = False
    return nodata_boolean

# Get gaze position and offset cutoff.
# Then check for the offset of gaze from the center screen.
def check_gaze_offset(gaze_position):
    gaze_center_offset = numpy.sqrt((gaze_position[0])**2 + (gaze_position[1])**2) #pythagoras theorem
    if gaze_center_offset >= gaze_offset_cutoff:
        offset_boolean = True
    else:
        offset_boolean = False
    return offset_boolean

# Fixation cross: Check for data availability and screen center gaze.
# for baseline 
def fixcross_gazecontingent(duration_in_seconds, background_color = background_color_rgb, cross_color = 'black'):
    # Translate duration to number of frames:
    number_of_frames = round(duration_in_seconds/refresh_rate)
    timestamp = core.getTime()
    gaze_offset_duration = 0
    pause_duration = 0
    nodata_duration = 0
    # Cross presentation for number of frames:
    for frameN in range(number_of_frames):
        # Check for keypress:
        pause_duration += check_keypress()
        # Check for eye tracking data, only call once per flip:
        gaze_position = tracker.getPosition()
        # Check for eye tracking data:
        if check_nodata(gaze_position):
            print('warning: no eyes detected')
            logging.warning(' NO EYES DETECTED')
            frameN = 1 # reset duration of for loop - resart ISI 
            nodata_current_duration = 0

            while check_nodata(gaze_position):
                mywin.flip() #wait for monitor refresh time
                nodata_duration += refresh_rate
                nodata_current_duration += refresh_rate
                gaze_position = tracker.getPosition() #get new gaze data
        # Check for gaze:
        elif check_gaze_offset(gaze_position):
            print('warning: gaze offset')
            frameN = 1 #reset duration of for loop - resart ISI

            while not check_nodata(gaze_position) and check_gaze_offset(gaze_position):
                # Listen for keypress:
                pause_duration += check_keypress()
                draw_fixcross(background_color, cross_color)
                draw_gazedirect(background_color) #redirect attention to fixation cross area
                mywin.flip() #wait for monitor refresh time
                gaze_offset_duration += refresh_rate
                gaze_position = tracker.getPosition() #get new gaze data
        
        # Draw fixation cross:
        draw_fixcross(background_color, cross_color)
        mywin.flip()

    # Generate output info:
    actual_fixcross_duration = round(core.getTime()-timestamp,3)
    gaze_offset_duration = round(gaze_offset_duration,3)
    nodata_duration = round(nodata_duration,3)

    print('numberof frames: ' + str(number_of_frames))
    logging.info(' NUMBER OF FRAMES: ' f'{number_of_frames}')
    print('no data duration: ' + str(nodata_duration))
    logging.info(' NO DATA DURATION: ' f'{nodata_duration}')
    print('gaze offset duration: ' + str(gaze_offset_duration))
    logging.info(' GAZE OFFSET DURATION: ' f'{gaze_offset_duration}')
    print('pause duration: ' + str(pause_duration))
    logging.info(' PAUSE DURATION: ' f'{pause_duration}')
    print('actual fixcross duration: ' + str(actual_fixcross_duration))
    logging.info(' ACTUAL FIXCROSS DURAION: ' f'{actual_fixcross_duration}')

    return [actual_fixcross_duration, gaze_offset_duration, pause_duration, nodata_duration]

def run_gazecontingent_ISI(isi_duration):
    isi_start_time = core.getTime()

    valid_time = 0.0
    gaze_offset_duration = 0.0
    nodata_duration = 0.0
    pause_duration = 0.0

    last_time = core.getTime()

    while valid_time < isi_duration:
        pause_duration += check_keypress()

        gaze = tracker.getPosition()
        current_time = core.getTime()
        dt = current_time - last_time
        last_time = current_time

        # no data
        if check_nodata(gaze):
            nodata_duration += dt
            draw_fixcross(background_color_rgb)
            mywin.flip()
            continue

        # gaze offset
        if check_gaze_offset(gaze):
            gaze_offset_duration += dt
            draw_fixcross(background_color_rgb)
            draw_gazedirect(background_color_rgb)
            mywin.flip()
            continue

        # valid gaze
        valid_time += dt
        draw_fixcross(background_color_rgb)
        mywin.flip()

    isi_end_time = core.getTime()

    # wall-clock ISI duration
    actual_duration = round(isi_end_time - isi_start_time, 3)

    return (
        actual_duration,          # TOTAL ISI duration 
        isi_start_time,
        isi_end_time,
        round(gaze_offset_duration, 3),
        round(pause_duration, 3),
        round(nodata_duration, 3)
    )

# ================================
# PRACTICE SETTINGS  
# ================================
# Single block of 20 trials, mirroring the main-trial ratio (60/20/10/10).
# All four stimulus types are used so children learn each image before the main task.
# If accuracy < 65% the whole block repeats (up to MAX_PRACTICE_REPEATS times).
 
N_PRACTICE_TRIALS   = 20
PRACTICE_GO_RATIO   = 0.60   # 12 go
PRACTICE_NOGO_DOM_RATIO   = 0.20   #  4 nogo_dom
PRACTICE_NOGO_RARE1_RATIO = 0.10   #  2 nogo_rare1
PRACTICE_NOGO_RARE2_RATIO = 0.10   #  2 nogo_rare2
 
# Derived trial counts (flooring; total guaranteed by construction below)
N_PRACTICE_GO       = int(N_PRACTICE_TRIALS * PRACTICE_GO_RATIO)        # 12
N_PRACTICE_NOGO_DOM = int(N_PRACTICE_TRIALS * PRACTICE_NOGO_DOM_RATIO)  #  4
N_PRACTICE_NOGO_RARE1 = int(N_PRACTICE_TRIALS * PRACTICE_NOGO_RARE1_RATIO)  # 2
N_PRACTICE_NOGO_RARE2 = (
    N_PRACTICE_TRIALS
    - N_PRACTICE_GO
    - N_PRACTICE_NOGO_DOM
    - N_PRACTICE_NOGO_RARE1
)  # remainder = 2, protects against rounding drift
 
assert N_PRACTICE_GO + N_PRACTICE_NOGO_DOM + N_PRACTICE_NOGO_RARE1 + N_PRACTICE_NOGO_RARE2 == N_PRACTICE_TRIALS, \
    "Practice trial counts do not sum to N_PRACTICE_TRIALS — check ratios."
 
PRACTICE_FEEDBACK_DURATION      = 0.6   # seconds
PERFORMANCE_CRITERION_ACCURACY  = 0.65  # 65 % correct across all 20 trials
MAX_PRACTICE_REPEATS             = 2     # max extra attempts (so up to 3 total)
 
# ================================
# MAIN TRIAL SETTINGS
# ================================
N_TRIALS_TOTAL = 200

# Trial counts per condition (60 / 20 / 10 / 10)
N_GO         = int(N_TRIALS_TOTAL * 0.60)  # 120
N_NOGO_DOM   = int(N_TRIALS_TOTAL * 0.20)  #  40  dominant nogo (fruit 1)
N_NOGO_RARE1 = int(N_TRIALS_TOTAL * 0.10)  #  20  rare nogo 1   (fruit 2)
N_NOGO_RARE2 = int(N_TRIALS_TOTAL * 0.10)  #  20  rare nogo 2   (fruit 3)

# Sanity check — catches any rounding issues
assert N_GO + N_NOGO_DOM + N_NOGO_RARE1 + N_NOGO_RARE2 == N_TRIALS_TOTAL, \
    "Trial counts do not sum to N_TRIALS_TOTAL — check ratios."

print(f"Trial distribution: go={N_GO}, nogo_dom={N_NOGO_DOM}, "
      f"nogo_rare1={N_NOGO_RARE1}, nogo_rare2={N_NOGO_RARE2}")
logging.info(f"Trial distribution: go={N_GO}, nogo_dom={N_NOGO_DOM}, "
             f"nogo_rare1={N_NOGO_RARE1}, nogo_rare2={N_NOGO_RARE2}")

MIN_FIXATION_DURATION = 0.1  # seconds (100 ms) to define a proper fixation on stimulus

# ================================
# PRACTICE TRIALS  [UNCHANGED — using single 'nogo' label for now]
# ================================
n_practice_go   = int(N_PRACTICE_TRIALS * PRACTICE_GO_RATIO)
n_practice_nogo = N_PRACTICE_TRIALS - n_practice_go

practice_trial_list = (
    [{'trial_type': 'go'}]   * n_practice_go +
    [{'trial_type': 'nogo'}] * n_practice_nogo
)

practice_trials = data.TrialHandler(
    practice_trial_list,
    nReps=1,
    method='random'
)

# ================================
# STIMULUS PRESENTATION
# ================================
def present_stimulus(stimulus_duration_in_seconds, trial, trial_number):
    kb.clearEvents()
    kb.clock.reset() # Reset keyboard clock to get reaction times relative to each trial start.
    
    stim_clock = core.Clock()

    stim_start = core.getTime()
    responded = False
    response_rt = None
    response_timestamp = None # absolute time of keypress (core.clock)

    # eye-tracking variables 
    first_fix_latency = None
    dwell_time = 0.0
    fixating = False
    fixation_start_time = None
    last_time = stim_clock.getTime()

    while stim_clock.getTime() < stimulus_duration_in_seconds:
        pause_duration = check_keypress()

        # --- Draw the correct stimulus using the lookup map ---
        # All four trial types are handled through STIMULUS_MAP.
        # For practice, 'nogo' maps to the dominant nogo stimulus as a placeholder
        # (will be updated when practice is redesigned).
        stim_to_draw = STIMULUS_MAP.get(trial, nogo_dom_stimulus)
        stim_to_draw.draw()

        # gaze processing 
        gaze = tracker.getPosition()
        current_time = stim_clock.getTime()
        dt = current_time - last_time
        last_time = current_time

        valid_gaze = (
            gaze is not None and
            not check_gaze_offset(gaze) and
            gaze_on_stimulus(gaze)
        )

        if valid_gaze:
            if not fixating:
                fixation_start_time = current_time
                fixating = True

            # fixation becomes "real" only after MIN_FIXATION_DURATION
            if (current_time - fixation_start_time) >= MIN_FIXATION_DURATION:
                if first_fix_latency is None:
                    first_fix_latency = fixation_start_time
                dwell_time += dt

        else:
            # fixation broken
            fixating = False
            fixation_start_time = None

        # gaze warning overlay
        if check_nodata(gaze):
            logging.warning('NO EYES DETECTED')
            draw_gazedirect(background_color_rgb)

        elif check_gaze_offset(gaze):
            logging.warning('GAZE OFFSET')
            draw_gazedirect(background_color_rgb)

        # flip once per frame 
        mywin.flip()
 
        # Response handling 
        keys = kb.getKeys([GO_KEY], waitRelease=False)
        if keys and not responded:
            responded = True
            response_rt = keys[0].rt # relative to trial/stimulus onset
            response_timestamp = core.getTime()
            # Response trigger: fires at the moment of keypress
            send_trigger([str(trial_number), trial + '_response', str(response_timestamp)])

    stim_end = core.getTime()
    stimulus_duration = stim_end - stim_start

    # --- Accuracy coding ---
    # 'go' = hit/miss; anything else is a nogo trial = correct_rejection/false_alarm
    if trial == 'go':
        accuracy = 'hit' if responded else 'miss'
    elif trial in ('nogo_dom', 'nogo_rare1', 'nogo_rare2', 'nogo'):
        accuracy = 'false_alarm' if responded else 'correct_rejection'
    else:
        accuracy = 'NA'

    # Store values as function attributes (unchanged interface)
    present_stimulus.accuracy = accuracy
    present_stimulus.response = responded
    present_stimulus.response_rt = response_rt
    present_stimulus.response_timestamp = response_timestamp
    present_stimulus.fixation_latency = first_fix_latency
    present_stimulus.dwell_time = dwell_time

    return stimulus_duration, stim_start, stim_end

# ================================
# EXPERIMENTAL DESIGN 
# ================================
# Phase handler
phase_sequence = ['baseline', 'practice', 'main_trials']
phase_handler = data.TrialHandler(phase_sequence, nReps=1, method='sequential')
exp.addLoop(phase_handler)

# Global variables:
trial_counter = 0
practice_trial_counter = 0
baseline_trial_counter = 1

# send LSL trigger - EXPERIMENT START TRIGGER
start_time = core.getTime()
send_trigger(['experiment_start', 'go_nogo', str(start_time)])

for phase in phase_handler:
    # ================================
    # BASELINE
    # ================================
    if phase == 'baseline':
        print(f'Start of baseline {baseline_trial_counter}')
        logging.info(f'Start of baseline {baseline_trial_counter}')
        timestamp = time.time()
        timestamp_exp = core.getTime()
        timestamp_tracker = tracker.trackerTime()

        send_trigger([str(baseline_trial_counter), 'baseline_start', str(core.getTime())])
        
        [stimulus_duration, offset_duration, pause_duration, nodata_duration] = fixcross_gazecontingent(baseline_duration)
        
        send_trigger([str(baseline_trial_counter), 'baseline_end', str(core.getTime())])

        phase_handler.addData('phase', phase)
        phase_handler.addData('baseline_trial_counter', baseline_trial_counter)
        phase_handler.addData('stimulus_duration', stimulus_duration)
        phase_handler.addData('gaze_offset_duration', offset_duration)
        phase_handler.addData('trial_pause_duration', pause_duration)
        phase_handler.addData('trial_nodata_duration', nodata_duration)
        phase_handler.addData('timestamp', timestamp)
        phase_handler.addData('timestamp_exp', timestamp_exp)

        baseline_trial_counter += 1
        print('end of baseline')
        logging.info('end of baseline.')
        exp.nextEntry()
    
    # ================================
    # PRACTICE
    # Single block of 20 trials (60/20/10/10), all four stimulus types, with feedback.
    # Repeats up to MAX_PRACTICE_REPEATS times if accuracy < 65%.
    # ================================
    elif phase == 'practice':
        send_trigger(['practice_start', 'go_nogo', str(core.getTime())])
 
        print('Start of practice trials')
        logging.info('Start of practice trials.')
 
        repeat_counter  = 0   # counts how many times the block has run (0-indexed)
        criterion_met   = False
 
        while not criterion_met and repeat_counter <= MAX_PRACTICE_REPEATS:
 
            # --- Build the 20-trial practice list (same ratio as main trials) ---
            practice_trial_list = (
                [{'trial_type': 'go'}]         * N_PRACTICE_GO         +
                [{'trial_type': 'nogo_dom'}]   * N_PRACTICE_NOGO_DOM   +
                [{'trial_type': 'nogo_rare1'}] * N_PRACTICE_NOGO_RARE1 +
                [{'trial_type': 'nogo_rare2'}] * N_PRACTICE_NOGO_RARE2
            )
 
            practice_trials = data.TrialHandler(
                practice_trial_list, nReps=1, method='random'
            )
            exp.addLoop(practice_trials)
 
            block_accuracy = []   # collects accuracy for every trial in this attempt
 
            for trial in practice_trials:
                practice_trial_counter += 1
                trial_type = trial['trial_type']
                ISI = define_ISI_interval()
 
                timestamp         = time.time()
                timestamp_exp     = core.getTime()
                timestamp_tracker = tracker.trackerTime()
 
                print(f"\n=== Practice Trial {practice_trial_counter} "
                      f"(attempt {repeat_counter + 1}/{MAX_PRACTICE_REPEATS + 1}) ===")
                print(f"Trial type: {trial_type.upper()}")
                print(f"Stimulus duration: {stimulus_duration_in_seconds} s | ISI: {ISI} s")
 
                logging.info(f"=== Practice Trial {practice_trial_counter} "
                             f"(attempt {repeat_counter + 1}/{MAX_PRACTICE_REPEATS + 1}) ===")
                logging.info(f"Trial type: {trial_type.upper()}")
                logging.info(f"Stimulus duration: {stimulus_duration_in_seconds} s | ISI: {ISI} s")
 
                stim_onset_time = core.getTime()
                send_trigger([str(practice_trial_counter), trial_type + '_onset', str(stim_onset_time)])
 
                stimulus_duration, stim_start, stim_end = present_stimulus(
                    stimulus_duration_in_seconds, trial_type, practice_trial_counter
                )
 
                accuracy = present_stimulus.accuracy
                block_accuracy.append(accuracy)
 
                # Show smiley / frowney feedback
                show_practice_feedback(accuracy)
 
                isi_duration, isi_start, isi_end, gaze_offset_duration, pause_duration, nodata_duration = \
                    run_gazecontingent_ISI(ISI)
 
                # --- Save trial data ---
                phase_handler.addData('phase', phase)
                practice_trials.addData('trial_counter',        practice_trial_counter)
                practice_trials.addData('practice_attempt',     repeat_counter + 1)
                practice_trials.addData('trial',                trial_type)
 
                practice_trials.addData('timestamp',            timestamp)
                practice_trials.addData('timestamp_exp',        timestamp_exp)
                practice_trials.addData('timestamp_tracker',    timestamp_tracker)
 
                practice_trials.addData('accuracy',             present_stimulus.accuracy)
                practice_trials.addData('response',             present_stimulus.response)
                practice_trials.addData('rt',                   present_stimulus.response_rt)
                practice_trials.addData('response_timestamp',   present_stimulus.response_timestamp)
 
                practice_trials.addData('fixation_latency',     present_stimulus.fixation_latency)
                practice_trials.addData('dwell_time',           present_stimulus.dwell_time)
 
                practice_trials.addData('ISI_expected',         ISI)
                practice_trials.addData('ISI_duration',         isi_duration)
                practice_trials.addData('ISI_start_time',       isi_start)
                practice_trials.addData('ISI_end_time',         isi_end)
 
                practice_trials.addData('gaze_offset_duration', gaze_offset_duration)
                practice_trials.addData('trial_pause_duration', pause_duration)
                practice_trials.addData('trial_nodata_duration',nodata_duration)
 
                practice_trials.addData('stimulus_duration',    stimulus_duration)
                practice_trials.addData('stimulus_start_time',  stim_start)
                practice_trials.addData('stimulus_end_time',    stim_end)
                practice_trials.addData('stim_onset_trigger_time', stim_onset_time)
 
                exp.nextEntry()
 
            # --- Criterion check across all 20 trials of this attempt ---
            n_correct     = sum(1 for a in block_accuracy if a in ('hit', 'correct_rejection'))
            accuracy_rate = n_correct / len(block_accuracy) if block_accuracy else 0.0
            criterion_met = accuracy_rate >= PERFORMANCE_CRITERION_ACCURACY
 
            print(f"\nPractice accuracy: {accuracy_rate:.1%} — "
                  f"{'criterion MET' if criterion_met else 'criterion NOT MET'}")
            logging.info(f"Practice accuracy: {accuracy_rate:.1%} — "
                         f"{'MET' if criterion_met else 'NOT MET'}")
 
            # If criterion not met and repeats remain, prompt experimenter / child
            if not criterion_met and repeat_counter < MAX_PRACTICE_REPEATS:
                visual.TextStim(
                    win=mywin, color='white',
                    text="Lass es uns nochmal versuchen! Drücke eine Taste, wenn du bereit bist."
                ).draw()
                mywin.flip()
                kb.waitKeys()
 
            repeat_counter += 1
 
        # Store summary info in the phase row
        phase_handler.addData('practice_criterion_met', criterion_met)
        phase_handler.addData('practice_attempts',      repeat_counter)
 
        end_practice = visual.TextStim(
            win=mywin, color='white',
            text='Übung beendet. Drücke eine Taste, um fortzufahren.'
        )
        end_practice.draw()
        mywin.flip()
        kb.waitKeys()
 
        send_trigger(['practice_end', 'go_nogo', str(core.getTime())])

    # ================================
    # MAIN TRIALS
    # ================================
    elif phase == 'main_trials':

        # --- Build 4-condition trial list (60 / 20 / 10 / 10) ---
        trial_list = (
            [{'trial_type': 'go'}]         * N_GO         +
            [{'trial_type': 'nogo_dom'}]   * N_NOGO_DOM   +
            [{'trial_type': 'nogo_rare1'}] * N_NOGO_RARE1 +
            [{'trial_type': 'nogo_rare2'}] * N_NOGO_RARE2
        )
        # TrialHandler with method='random' shuffles the list independently for each participant
        trials = data.TrialHandler(trial_list, nReps=1, method='random')
        exp.addLoop(trials)

        send_trigger(['main_trials_start', 'go_nogo', str(core.getTime())])

        for trial in trials:
            trial_type = trial['trial_type']
            ISI = define_ISI_interval()
            timestamp = time.time()
            timestamp_exp = core.getTime()
            timestamp_tracker = tracker.trackerTime()

            # Increment counter at start
            trial_counter += 1

            # --- Mid-task break after trial 100 ---
            if trial_counter == 101:  # fires before trial 101, i.e. after trial 100 is complete
                send_trigger(['break_start', 'go_nogo', str(core.getTime())])
                break_start_time = core.getTime()
                break_duration = 120  # 2 minutes
                halfway_shown = False

                while core.getTime() - break_start_time < break_duration:
                    elapsed = core.getTime() - break_start_time
                    remaining = break_duration - elapsed
                    remaining_int = int(remaining)

                    print(f"\rBreak: {remaining_int} seconds remaining...", end='', flush=True)

                    if elapsed >= 60 and not halfway_shown:
                        halfway_shown = True

                    if not halfway_shown:
                        visual.TextStim(win=mywin, color='white', text='Pause!').draw()
                    elif remaining <= 10:
                        visual.TextStim(
                            win=mywin,
                            color='white',
                            text=f'Es geht weiter in {remaining_int} Sekunden...'
                        ).draw()
                    else:
                        visual.TextStim(win=mywin, color='white', text='Halbzeit!').draw()

                    mywin.flip()

                print()
                send_trigger(['break_end', 'go_nogo', str(core.getTime())])

            # --- Console + log ---
            print(f"\n=== Trial {trial_counter}/{N_TRIALS_TOTAL} ===")
            print(f"Trial type: {trial_type.upper()}")
            print(f"Stimulus duration: {stimulus_duration_in_seconds} s")
            print(f"ISI: {ISI} s")
            print(f"Gaze position: {tracker.getPosition()}")

            logging.info(f"=== Trial {trial_counter}/{N_TRIALS_TOTAL}")
            logging.info(f"Trial type: {trial_type.upper()}")
            logging.info(f"Stimulus duration (planned): {stimulus_duration_in_seconds} s")
            logging.info(f"ISI: {ISI} s")
            logging.info(f"Gaze position: {tracker.getPosition()}")

            # --- Stimulus onset trigger ---
            stim_onset_time = core.getTime()
            send_trigger([str(trial_counter), trial_type + '_onset', str(stim_onset_time)])

            stimulus_duration, stim_start, stim_end = present_stimulus(
                stimulus_duration_in_seconds, trial_type, trial_counter
            )

            # --- ISI ---
            isi_duration, isi_start, isi_end, gaze_offset_duration, pause_duration, nodata_duration = run_gazecontingent_ISI(ISI)

            # --- Save data ---
            phase_handler.addData('phase', phase)

            trials.addData('trial_counter', trial_counter)
            trials.addData('trial', trial_type)

            trials.addData('timestamp', timestamp)
            trials.addData('timestamp_exp', timestamp_exp)
            trials.addData('timestamp_tracker', timestamp_tracker)

            trials.addData('accuracy', present_stimulus.accuracy)
            trials.addData('response', present_stimulus.response)
            trials.addData('rt', present_stimulus.response_rt)
            trials.addData('response_timestamp', present_stimulus.response_timestamp)
            trials.addData('fixation_latency', present_stimulus.fixation_latency)
            trials.addData('dwell_time', present_stimulus.dwell_time)

            trials.addData('ISI_expected', ISI)
            trials.addData('ISI_duration', isi_duration)
            trials.addData('ISI_start_time', isi_start)
            trials.addData('ISI_end_time', isi_end)

            trials.addData('gaze_offset_duration', gaze_offset_duration)
            trials.addData('trial_pause_duration', pause_duration)
            trials.addData('trial_nodata_duration', nodata_duration)

            trials.addData('stimulus_duration', stimulus_duration)
            trials.addData('stimulus_start_time', stim_start)
            trials.addData('stimulus_end_time', stim_end)
            trials.addData('stim_onset_trigger_time', stim_onset_time)

            exp.nextEntry()

# ================================
# WRAP UP AND CLOSE
# ================================
end_time = core.getTime()
send_trigger(['experiment_end', 'go_nogo', str(end_time)])

print('EXPERIMENT ENDED')
print(f"Total duration: {end_time - start_time:.2f} seconds")
logging.info('EXPERIMENT ENDED.')

tracker.setRecordingState(False)
io.quit()
mywin.close()
core.quit()