"""
Dot Probe Task 
-----------------------------------------------------
- Fixation: 500 ms (gaze-contingent)
- Face pair: 500 ms 
- Probe (dot): 1250 ms
- Intertrial interval (blank): 300–800 ms
- Conditions: angry–neutral and happy–neutral (+ filler neutral neutral)
- Congruent = probe appears on same side as emotional face
- FREE VIEWING task: no behavioral response required
- Uses mouse as fake eye-tracker (move mouse cursor to simulate gaze) when testmode is True
- (stim_duration = planned duration; stimulus_duration = actual stimulus duration)
"""
 
# LOAD MODULES-
import os
import random
import itertools
import csv
import time
import numpy 
from pathlib import Path
from psychopy import visual, core, event, clock, data, gui, monitors
import tobii_research as tr  # keep if you have Tobii. If not, you'll be in testmode.
from psychopy.iohub import launchHubServer
from psychopy.hardware import keyboard
from psychopy.monitors import Monitor
import logging
from datetime import datetime
import json
import sys
 
#Load config file 
with open("tasks/config.json", "r") as file: 
    config = json.load(file)
 
# media paths
base_path = Path(config["task_base_path"])
faces_path = base_path / config["media"]["faces"]
 
# select logging 
task_name = "dot_probe"
task_config = config["tasks"][task_name]
constants = config["constants"]
 
'''SETUP'''
# SETUP logging paths and filenames 
current_datetime = datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H-%M-%S")
logging_path = Path(task_config["logging"]["base_path"], task_config["logging"]["log_folder"]).resolve()
filename_dot_probe = os.path.join(logging_path, formatted_datetime)
 
# check if directory exists
if not logging_path.exists():
    # If it doesnt exist, create it
    logging_path.mkdir(parents=True, exist_ok=True)
else:
    print(f"Directory {logging_path} already exists. Continuing to use it.")
 
logging.basicConfig(
    level = logging.DEBUG,
    filename = filename_dot_probe,
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
testmode_et = config["constants"]["eyetracker"]["testmode"]
sampling_rate = config["constants"]["eyetracker"].get("sampling_rate", 60)
background_color_rgb = config["constants"]["psychopy_window"]["background_color"]
size_fixation_cross_in_pixels = config["constants"]["psychopy_window"]["size_fixation_cross_in_pixels"]
 
# Participant/timepoint from CLI or dialog fallback:
try:
    participant_id = sys.argv[1]
    timepoint = sys.argv[2]
except Exception:
    dlg = gui.Dlg(title="Participant info")
    dlg.addField("participant_id:")
    dlg.addField("timepoint:")
    ok_data = dlg.show()
    if dlg.OK:
        participant_id = ok_data[0]
        timepoint = ok_data[1]
    else:
        raise RuntimeError("No participant ID provided — aborting.")
 
selected_timepoint = timepoint
 
fileName = f'{task_name}_{participant_id}_{selected_timepoint}_{data.getDateStr(format="%Y-%m-%d-%H%M")}'
 
filename_dot_probe = str(logging_path / (fileName + ".log"))
logging.basicConfig(
    level=logging.DEBUG,
    filename=filename_dot_probe,
    filemode='w',
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s'
)
 
trials_data_folder = Path(task_config["data_paths"]["trials"]).resolve()
eyetracking_data_folder = Path(task_config["data_paths"]["eyetracking"]).resolve()
trials_data_folder.mkdir(parents=True, exist_ok=True)
eyetracking_data_folder.mkdir(parents=True, exist_ok=True)
 
print(f"THIS IS {task_name.upper()}")
logging.info(f"THIS IS {task_name.upper()}")
 
# CONSTANTS 
# Experimental settings
dialog_screen = config["constants"]["dialog_screen"]
presentation_screen = config["constants"]["presentation_screen"]
current_screen = presentation_screen
fixation_duration_in_seconds = 0.5
probe_duration_in_seconds = 1.25
ISI_interval = [0.30, 0.80]  # seconds
gaze_offset_cutoff = 3 * size_fixation_cross_in_pixels
baseline_duration = 5
no_data_warning_cutoff = 0.5
settings = {}
 
# Experiment handler
exp = data.ExperimentHandler(
    name=task_name,
    version='0.3',
    extraInfo=settings,
    dataFileName=str(trials_data_folder / fileName),
)
 
MONITOR_NAME = config["constants"]["monitor"]["name"]
mon = Monitor(MONITOR_NAME)
mon.setWidth(config["constants"]["monitor"]["width_cm"])
mon.setDistance(config["constants"]["monitor"]["distance_cm"])
mon.setSizePix([config["constants"]["monitor"]["width"], config["constants"]["monitor"]["height"]])
 
mywin = visual.Window(
    size=(config["constants"]["monitor"]["width"], config["constants"]["monitor"]["height"]),
    fullscr=config["constants"]["psychopy_window"]["fullscreen"],
    screen=config["constants"]["presentation_screen"],
    color=config["constants"]["psychopy_window"]["background_color"],
    monitor=MONITOR_NAME,
    units='pix'
)
 
refresh_rate = mywin.monitorFramePeriod
print('monitor refresh rate: ' + str(round(refresh_rate, 4)) + ' seconds')
 
# Face size
face_size = (600, 770)
 
# Define Areas of Interest (AOIs) based on image and asterisks positions and sizes
# AOI settings
show_AOIs = False # set to false for real data collection
 
stim_x_offset = 500
stim_y = 0
aoi_margin = 50 
aoi_width = face_size[0] + aoi_margin # 600 + 50 = 650
aoi_height = face_size[1] + aoi_margin 
 
AOI_left = visual.Rect(
    win=mywin,
    width=aoi_width,
    height=aoi_height,
    pos=[-stim_x_offset, stim_y],
    lineColor='blue',
    lineWidth=3,
    fillColor=None,
    opacity=0.5
)
 
AOI_right = visual.Rect(
    win=mywin,
    width=aoi_width,
    height=aoi_height,
    pos=[stim_x_offset, stim_y],
    lineColor='orange',
    lineWidth=3,
    fillColor=None,
    opacity=0.5
)
 
# Probe AOIs (smaller, dot-centered)
probe_radius = size_fixation_cross_in_pixels
 
probe_AOI_left = visual.Circle(
    win=mywin,
    radius=probe_radius,
    pos=[-stim_x_offset, stim_y],
    lineColor='green',
    fillColor=None,
    opacity=0.5
)
 
probe_AOI_right = visual.Circle(
    win=mywin,
    radius=probe_radius,
    pos=[stim_x_offset, stim_y],
    lineColor='red',
    fillColor=None,
    opacity=0.5
)
 
def draw_face_AOIs():
    if show_AOIs:
        AOI_left.draw()
        AOI_right.draw()
 
def draw_probe_AOI(probe_side):
    if show_AOIs:
        if probe_side == "left":
            probe_AOI_left.draw()
        else:
            probe_AOI_right.draw()
        
def point_in_aoi(gaze_x, gaze_y, aoi):
    """Check whether a gaze sample (x, y) is inside a given AOI."""
    left, right = aoi.pos[0] - aoi.width / 2, aoi.pos[0] + aoi.width / 2
    bottom, top = aoi.pos[1] - aoi.height / 2, aoi.pos[1] + aoi.height / 2
    return left <= gaze_x <= right and bottom <= gaze_y <= top
 
def point_in_circle(x, y, circle):
    dx = x - circle.pos[0]
    dy = y - circle.pos[1]
    return (dx**2 + dy**2) <= circle.radius**2
 
def analyze_gaze_for_trial(gaze_data, AOI_left, AOI_right, face_onset, face_offset, probe_onset=None, probe_pos=None):
    """
    Compute gaze-based attention bias metrics:
      - initial fixation side (emotional or neutral)
      - dwell time per AOI, accumulated at refresh_rate per sample
        (consistent with fixcross_gazecontingent and run_ISI)
      - latency to first fixation on probe AOI (if probe_onset provided)
    gaze_data: list of (timestamp, x, y)
    """
    # --- Face period samples only ---
    face_samples = [g for g in gaze_data if face_onset <= g[0] <= face_offset]
 
    dwell_left, dwell_right = 0.0, 0.0
    first_fixation_side = None
 
    for t, x, y in face_samples:
        in_left  = point_in_aoi(x, y, AOI_left)
        in_right = point_in_aoi(x, y, AOI_right)
 
        # First fixation side
        if first_fixation_side is None:
            if in_left:
                first_fixation_side = "left"
            elif in_right:
                first_fixation_side = "right"
 
        # Each sample spans one frame — consistent with refresh_rate-based
        # accumulation used elsewhere in the task (fixcross_gazecontingent, run_ISI)
        if in_left:
            dwell_left += refresh_rate
        elif in_right:
            dwell_right += refresh_rate
 
    dwell_bias = dwell_right - dwell_left  # positive = right bias
 
    # --- Probe fixation latency ---
    probe_fixation_latency = None
 
    if probe_onset is not None:
        probe_samples = [g for g in gaze_data if g[0] >= probe_onset]
 
        for t, x, y in probe_samples:
            if probe_pos == "left":
                in_probe = point_in_circle(x, y, probe_AOI_left)
            else:
                in_probe = point_in_circle(x, y, probe_AOI_right)
 
            if in_probe:
                probe_fixation_latency = t - probe_onset
                break  # first fixation only
 
    return first_fixation_side, dwell_left, dwell_right, dwell_bias, probe_fixation_latency
 
 
# Build trials
# we now randomize which side the emotional face appears on and set congruency accordingly
# 32 critical trials (16 angry-neutral and 16 happy-neutral)
# + optional 8-neutral filler trials (not analysed)
# Build trials
# -----------------------------
# SETTINGS
# -----------------------------
 
models = ["01F", "18F", "36M", "40M"]
 
conditions = ["angry-neutral", "happy-neutral"]
 
emo_sides = ["left", "right"]
 
congruencies = ["congruent", "incongruent"]
 
stim_duration = 0.5 # planned duration 
 
n_fillers = 8
 
trials = []
 
# -----------------------------
# CRITICAL TRIALS
# 4 x 2 x 2 x 2 = 32
# -----------------------------
 
critical_design = list(itertools.product(
    models,
    conditions,
    emo_sides,
    congruencies
))
 
for model, condition, emo_side, congruency in critical_design:
 
    if condition == "angry-neutral":
        emo_label = "angry"
    else:
        emo_label = "happy"
 
    # Probe location depends on congruency
    if congruency == "congruent":
        probe_side = emo_side
    else:
        probe_side = "right" if emo_side == "left" else "left"
 
    trial = {
        "trial_type": "critical",
        "model": model,
        "condition": condition,
        "emo_label": emo_label,
        "emo_side": emo_side,
        "congruency": congruency,
        "probe_side": probe_side,
        "stim_duration": stim_duration
    }
 
    trials.append(trial)
 
# -----------------------------
# FILLER TRIALS
# neutral-neutral
# -----------------------------
 
# each model appears twice
filler_models = models * 2
 
for model in filler_models:
 
    probe_side = random.choice(["left", "right"])
 
    trial = {
        "trial_type": "filler",
        "model": model,
        "condition": "neutral-neutral",
        "emo_label": "neutral",
        "emo_side": None,
        "congruency": None,
        "probe_side": probe_side,
        "stim_duration": stim_duration
    }
 
    trials.append(trial)
 
# -----------------------------
# FINAL RANDOMIZATION
# -----------------------------
 
random.shuffle(trials)
 
# total trials
number_of_trials = len(trials)
print(len(trials))  # 40
 
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
 
# SETUP KEYBOARD (for pause/escape only — no response keys needed in free viewing)
kb = keyboard.Keyboard()
 
 
# Draw a fixation cross from lines:
def draw_fixcross(background_color=background_color_rgb, cross_color='black'):
    if background_color is not background_color_rgb:
        background_rect = visual.Rect(win=mywin, size=mywin.size, fillColor=background_color)
        background_rect.draw()
    line1 = visual.Line(win=mywin, units='pix', lineColor=cross_color)
    line1.start = [-(size_fixation_cross_in_pixels / 2), 0]
    line1.end = [+(size_fixation_cross_in_pixels / 2), 0]
    line2 = visual.Line(win=mywin, units='pix', lineColor=cross_color)
    line2.start = [0, -(size_fixation_cross_in_pixels / 2)]
    line2.end = [0, +(size_fixation_cross_in_pixels / 2)]
    line1.draw()
    line2.draw()
 
# Draw figure when gaze is offset for gaze contigency:
def draw_gazedirect(background_color=background_color_rgb):
    # Adapt background according to provided "background_color"
    if background_color is not background_color_rgb:
        background_rect = visual.Rect(
            win = mywin,
            size = mywin.size,
            fillColor = background_color)
        background_rect.draw()
    function_color = 'red'
    arrow_size_pix = size_fixation_cross_in_pixels
    arrow_pos_offset = 5
    width = 3
 
    rect1 = visual.Rect(
        win = mywin,
        units = 'pix',
        lineColor = function_color,
        fillColor = background_color,
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
 
# Check for keypress, used to pause and quit experiment:
def check_keypress():
    global current_screen
    keys = kb.getKeys(['p','escape'], waitRelease = True)
    timestamp_keypress = clock.getTime()
 
    key_names = [key.name for key in keys]
 
    if 'escape' in key_names:
        dlg = gui.Dlg(title='Quit?', labelButtonOK=' OK ', labelButtonCancel=' Cancel ')
        dlg.addText('Do you really want to quit? - Then press OK')
        dlg.screen = dialog_screen
        dlg.show()
        if dlg.OK:
            print('EXPERIMENT ABORTED!')
            core.quit()
        else:
            print('Experiment continues...')
            current_screen = presentation_screen
        pause_time = clock.getTime() - timestamp_keypress
 
    elif 'p' in key_names:
        dlg = gui.Dlg(title='Pause', labelButtonOK='Continue')
        dlg.addText('Experiment is paused - Press Continue, when ready')
        dlg.screen = dialog_screen
        dlg.show()
        pause_time = clock.getTime() - timestamp_keypress
    else:
        pause_time = 0
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
                nodata_current_duration
                draw_gazedirect(background_color) #redirect attention to fixation cross area
                mywin.flip()  # Wait for monitor refresh time
                nodata_duration += refresh_rate
                nodata_current_duration += refresh_rate
                gaze_position = tracker.getPosition()  # Get new gaze data
 
            while check_nodata(gaze_position):
                mywin.flip() #wait for monitor refresh time
                nodata_duration += refresh_rate
                nodata_current_duration += refresh_rate
                gaze_position = tracker.getPosition() #get new gaze data
 
        # Check for gaze:
        elif check_gaze_offset(gaze_position):
            print('warning: gaze offset')
            frameN = 1 #reset duration of for loop - restart ISI
 
            while not check_nodata(gaze_position) and check_gaze_offset(gaze_position):
                # Listen for keypress:
                pause_duration += check_keypress()
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
 
# Interstimulus interval
def run_ISI(duration_in_seconds,
            background_color=background_color_rgb,
            cross_color='black'):
    """
    Run gaze-contingent ISI using the same fixation logic as baseline.
    """
    isi_start = core.getTime()
 
    (
        actual_duration,
        gaze_offset_duration,
        pause_duration,
        nodata_duration
    ) = fixcross_gazecontingent(
        duration_in_seconds,
        background_color=background_color,
        cross_color=cross_color
    )
 
    isi_end = core.getTime()
 
    return (
        actual_duration,
        round(isi_start, 3),
        round(isi_end, 3),
        gaze_offset_duration,
        pause_duration,
        nodata_duration
    )
 
# build image paths
emotion_code = {
    "angry": "AN",
    "happy": "HA",
    "neutral": "NE"
}
 
def get_face_image(model, emotion):
    """
    Returns the full path to a face image.
    Example: 01F_AN_C.BMP
    """
    filename = f"{model}_{emotion_code[emotion]}_C_schwarzweiß.png"
    return faces_path / filename
 
def make_face_stim(model, emotion, pos):
    return visual.ImageStim(
        win=mywin,
        image=str(get_face_image(model, emotion)),
        size=face_size,
        pos=pos
    )
 
def present_dotprobe_stimulus(trial, collect_gaze=True):
    """
    Show face pair and probe in correct order, collect gaze samples.
    Trial structure: face pair → probe (free viewing, no response required)
    Returns timestamps: face_onset, face_offset, probe_onset, probe_offset
    """
    stim_x_offset = 500
    stim_y = 0
 
    model = trial["model"]
    emo_label = trial["emo_label"]
    emo_side = trial["emo_side"]
 
    # --- Create face stimuli ---
    if emo_side == "left":
        left_face = make_face_stim(model, emo_label, [-stim_x_offset, stim_y])
        right_face = make_face_stim(model, "neutral", [stim_x_offset, stim_y])
 
    elif emo_side == "right":
        left_face = make_face_stim(model, "neutral", [-stim_x_offset, stim_y])
        right_face = make_face_stim(model, emo_label, [stim_x_offset, stim_y])
 
    else:  # neutral-neutral filler
        left_face = make_face_stim(model, "neutral", [-stim_x_offset, stim_y])
        right_face = make_face_stim(model, "neutral", [stim_x_offset, stim_y])
 
    gaze_samples = []
 
    # --- Phase 1: Face pair ---
    face_onset = core.getTime()
    face_clock = core.Clock()
 
    while face_clock.getTime() < trial["stim_duration"]:
        left_face.draw()
        right_face.draw()
 
        # fixation cross stays visible during stimulus presentation
        draw_fixcross()
 
        draw_face_AOIs()
 
        if collect_gaze and tracker:
            pos = tracker.getPosition()
            if pos is not None:
                gaze_samples.append((core.getTime(), pos[0], pos[1]))
 
        mywin.flip()
 
    face_offset = core.getTime()
 
    # --- Phase 2: Probe (free viewing — no response required) ---
    probe_pos = (
        [-stim_x_offset, stim_y]
        if trial["probe_side"] == "left"
        else [stim_x_offset, stim_y]
    )
 
    # Use a circle (dot)
    probe_stim = visual.Circle(
        win=mywin,
        radius=size_fixation_cross_in_pixels / 2,
        fillColor='black',
        lineColor='black',
        pos=probe_pos
    )
 
    probe_onset = core.getTime()
    probe_clock = core.Clock()
 
    while probe_clock.getTime() < probe_duration_in_seconds:
        probe_stim.draw()
        draw_probe_AOI(trial["probe_side"])
 
        if collect_gaze and tracker:
            pos = tracker.getPosition()
            if pos is not None:
                gaze_samples.append((core.getTime(), pos[0], pos[1]))
 
        mywin.flip()
 
    probe_offset = core.getTime()
 
    return face_onset, face_offset, probe_onset, probe_offset, gaze_samples
 
 
# EXPERIMENTAL DESIGN 
# 32 critical trials (16 angry-neutral, 16 happy-neutral)
# +  8 neutral-neutral filler trials (not analysed)
start_time = core.getTime()
trial_counter = 0
 
# phase 0 baseline fixation cross (before trials)
def show_baseline_fixation():
    print("Displaying Baseline Fixation Cross for 5 seconds.")
    timestamp_exp = core.getTime()
    fixcross_gazecontingent(5.0)
    logging.info("Baseline fixation cross displayed for 5 seconds")
 
show_baseline_fixation()  # <-- call it here
 
# --- Setup TrialHandler ---
trials_handler = data.TrialHandler(trialList=trials, nReps=1, method='sequential')
exp.addLoop(trials_handler)
 
# Add AOI metric fields once (not inside the loop)
trials_handler.data.addDataType('initial_fixation_side')
trials_handler.data.addDataType('dwell_left')
trials_handler.data.addDataType('dwell_right')
trials_handler.data.addDataType('dwell_bias')
trials_handler.data.addDataType('probe_fixation_latency')
 
# --- Trial loop ---
trial_counter = 0
 
try:
    for trial in trials_handler:
        trial_counter += 1
        ISI = random.uniform(ISI_interval[0], ISI_interval[1])
 
        # Preserve original timestamps
        timestamp = time.time()
        timestamp_exp = core.getTime()
        try:
            timestamp_tracker = tracker.trackerTime()
        except Exception:
            timestamp_tracker = None
 
        logging.info(f'NEW TRIAL {trial_counter} - {trial["condition"]}')
 
        # --- Console + log display of trial info ---
        print(f"\n=== Trial {trial_counter}/{number_of_trials} ===")
        print(f"Condition: {trial['condition']}")
        print(f"Congruency: {trial['congruency']}")
        print(f"Emotional face side: {trial['emo_side']}")
        print(f"Probe side: {trial['probe_side']}")
        print(f"Stimulus duration: {trial['stim_duration']} s")
 
        logging.info(f"=== Trial {trial_counter}/{number_of_trials} ===")
        logging.info(f"Condition: {trial['condition']}")
        logging.info(f"Congruency: {trial['congruency']}")
        logging.info(f"Emotional face side: {trial['emo_side']}")
        logging.info(f"Probe side: {trial['probe_side']}")
        logging.info(f"Stimulus duration: {trial['stim_duration']} s")
 
        # --- Phase 0: Fixation cross (gaze-contingent) ---
        fix_durations = fixcross_gazecontingent(fixation_duration_in_seconds)
 
        # --- Phase 1 & 2: Face pair + probe (free viewing) ---
        # Trial order: fixation → faces → probe → ISI
        face_onset, face_offset, probe_onset, probe_offset, gaze_samples = present_dotprobe_stimulus(trial, collect_gaze=True)
 
        # --- Analyze gaze samples for AOI metrics ---
        first_fixation_side, dwell_left, dwell_right, dwell_bias, probe_fix_latency = analyze_gaze_for_trial(
            gaze_samples,
            AOI_left,
            AOI_right,
            face_onset,
            face_offset,
            probe_onset,
            trial['probe_side']
        )
 
        # --- Phase 3: ISI ---
        isi_duration, ISI_onset, isi_end, gaze_offset_duration, pause_duration, nodata_duration = run_ISI(ISI)
 
        # --- Save trial data ---
        trials_handler.addData('trial_num', trial_counter)
        trials_handler.addData('condition', trial['condition'])
        trials_handler.addData('congruency', trial['congruency'])
        trials_handler.addData('probe_side', trial['probe_side'])
        trials_handler.addData('timestamp', timestamp)
        trials_handler.addData('timestamp_exp', timestamp_exp)
        trials_handler.addData('timestamp_tracker', timestamp_tracker)
 
        # Fixation durations
        trials_handler.addData('fix_actual_duration', fix_durations[0])
        trials_handler.addData('fix_gaze_offset_duration', fix_durations[1])
        trials_handler.addData('fix_pause_duration', fix_durations[2])
        trials_handler.addData('fix_nodata_duration', fix_durations[3])
 
        # Face & probe timestamps
        trials_handler.addData('face_onset', face_onset)
        trials_handler.addData('face_offset', face_offset)
        trials_handler.addData('probe_onset', probe_onset)
        trials_handler.addData('probe_offset', probe_offset)
        trials_handler.addData('stimulus_duration_used', trial['stim_duration'])
 
        # ISI
        trials_handler.addData('ISI_expected', ISI)
        trials_handler.addData('ISI_onset', ISI_onset)
        trials_handler.addData('ISI_duration', isi_duration)
        trials_handler.addData('ISI_offset', isi_end)
        trials_handler.addData('ISI_gaze_offset_duration', gaze_offset_duration)
        trials_handler.addData('ISI_pause_duration', pause_duration)
        trials_handler.addData('ISI_nodata_duration', nodata_duration)
 
        # Trial info
        trials_handler.addData('filler', trial['trial_type'] == 'filler')
 
        # AOI gaze metrics
        trials_handler.addData('initial_fixation_side', first_fixation_side)
        trials_handler.addData('dwell_left', dwell_left)
        trials_handler.addData('dwell_right', dwell_right)
        trials_handler.addData('dwell_bias', dwell_bias)
        trials_handler.addData('probe_fixation_latency', probe_fix_latency)
 
        # Commit trial
        exp.nextEntry()
 
finally:
    # --- End of task cleanup ---
    end_time = core.getTime()
    logging.info(f"DOT PROBE TASK ENDED — Total duration: {end_time - start_time:.2f} seconds")
    print(f"DOT PROBE TASK ENDED — Total duration: {end_time - start_time:.2f} seconds")
 
    try:
        if tracker:
            tracker.setRecordingState(False)
        if io:
            io.quit()
    except Exception as e:
        logging.warning(f"Error during shutdown: {e}")
 
    try:
        exp.saveAsWideText(str(trials_data_folder / f"{fileName}.csv"))
        print("Trials data saved successfully.")
    except Exception as e:
        print("Error saving trials data:", e)
 
    mywin.close()
    core.quit()