#!/usr/bin/env python3

import ctypes
import os
import configparser

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import i3ipc
import copy
import signal
import sys
import traceback
import pprint
import time
import argparse
import math
import logging
import timing
from threading import Thread
from PIL import Image, ImageDraw

from xdg.BaseDirectory import xdg_config_home

pp = pprint.PrettyPrinter(indent=4)

global_updates_running = True
global_knowledge = {'active': 0}

pygame.display.init()
pygame.font.init()
i3 = i3ipc.Connection()

screenshot_lib = '/usr/share/i3expo/prtscn.so'
# screenshot_lib_path = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + screenshot_lib
grab = ctypes.CDLL(screenshot_lib)

timer = timing.get_timing_group(__name__)

# PARSE ARGUMENTS
parser = argparse.ArgumentParser(description="Display an overview of all open workspaces")
parser.add_argument("-v", "--verbose", help="Print more program data", action='store_true')
parser.add_argument("-i", "--interval", help="Update interval in seconds (default: 1s)")
parser.add_argument("-d", "--dedicated", help="Launch on a dedicated workspace", action="store_true")
args = parser.parse_args()

logLevel = logging.INFO
if args.verbose:
    logLevel = logging.DEBUG
    
logging.basicConfig(format='[%(levelname)s] %(asctime)s: %(message)s', level=logLevel)


def signal_quit(signal, frame):
    logging.info("Shutting down...")
    pygame.display.quit()
    pygame.quit()
    i3.main_quit()
    sys.exit(0)

def signal_reload(signal, frame):
    read_config()

def signal_show(signal, frame):
    global global_updates_running
    if not global_updates_running:
        global_updates_running = True
    else:
        source = i3.get_tree().find_focused().workspace().name
        if args.dedicated:
            i3.command('workspace i3expod-temporary-workspace')
        
        global_updates_running = False
        ui_thread = Thread(target = show_ui, args=[source])
        ui_thread.daemon = True
        ui_thread.start()

signal.signal(signal.SIGINT, signal_quit)
signal.signal(signal.SIGTERM, signal_quit)
signal.signal(signal.SIGHUP, signal_reload)
signal.signal(signal.SIGUSR1, signal_show)

config = configparser.RawConfigParser()

def get_color(section = None, option = None, raw = None):
    if not raw:
        raw = config.get(section, option)

    try:
        return pygame.Color(*raw)
    except (ValueError, TypeError):
        pass

    try:
        return pygame.Color(raw)
    except ValueError:
        pass

    if raw[0] == '#' and len(raw[1:]) == 3:
        try:
            r = int(raw[1], 16)
            g = int(raw[2], 16)
            b = int(raw[3], 16)
            return pygame.Color(r * 16, g * 16, b * 16, 255)
        except ValueError:
            pass

    if raw[0] == '#' and len(raw[1:]) == 6:
        try:
            r = int(raw[1:2], 16)
            g = int(raw[3:4], 16)
            b = int(raw[5:6], 16)
            return pygame.Color(r, g, b, 255)
        except ValueError:
            pass

    raise ValueError
  
    #except Exception as e:
    #    print traceback.format_exc()

defaults = {
        ('Capture', 'screenshot_width'): (config.getint, pygame.display.Info().current_w),
        ('Capture', 'screenshot_height'): (config.getint, pygame.display.Info().current_h),
        ('Capture', 'screenshot_offset_x'): (config.getint, 0),
        ('Capture', 'screenshot_offset_y'): (config.getint, 0),

        ('UI', 'window_width'): (config.getint, pygame.display.Info().current_w),
        ('UI', 'window_height'): (config.getint, pygame.display.Info().current_h),
        ('UI', 'bgcolor'): (get_color, get_color(raw = 'gray20')),
        ('UI', 'workspaces'): (config.getint, None),
        ('UI', 'grid_x'): (config.getint, None),
        ('UI', 'padding_percent_x'): (config.getint, 5),
        ('UI', 'padding_percent_y'): (config.getint, 5),
        ('UI', 'spacing_percent_x'): (config.getint, 5),
        ('UI', 'spacing_percent_y'): (config.getint, 5),
        ('UI', 'frame_width_px'): (config.getint, 5),
        ('UI', 'frame_active_color'): (get_color, get_color(raw = '#3b4f8a')),
        ('UI', 'frame_inactive_color'): (get_color, get_color(raw = '#43747b')),
        ('UI', 'frame_unknown_color'): (get_color, get_color(raw = '#c8986b')),
        ('UI', 'frame_empty_color'): (get_color, get_color(raw = 'gray60')),
        ('UI', 'frame_nonexistant_color'): (get_color, get_color(raw = 'gray30')),
        ('UI', 'tile_active_color'): (get_color, get_color(raw = '#5a6da4')),
        ('UI', 'tile_inactive_color'): (get_color, get_color(raw = '#93afb3')),
        ('UI', 'tile_unknown_color'): (get_color, get_color(raw = '#ffe6d0')),
        ('UI', 'tile_empty_color'): (get_color, get_color(raw = 'gray80')),
        ('UI', 'tile_nonexistant_color'): (get_color, get_color(raw = 'gray40')),
        ('UI', 'names_show'): (config.getboolean, 'True'),
        ('UI', 'names_font'): (config.get, 'sans-serif'),
        ('UI', 'names_fontsize'): (config.getint, 25),
        ('UI', 'names_color'): (get_color, get_color(raw = 'white')),
        ('UI', 'thumb_stretch'): (config.getboolean, 'False'),
        ('UI', 'highlight_percentage'): (config.getint, 20),
        ('UI', 'switch_to_empty_workspaces'): (config.getboolean, 'False'),
}

def read_config():
    config.read(os.path.join(xdg_config_home, "i3expo", "config"))
    for option in defaults.keys():
        if not isset(option):
            if defaults[option][1] == None:
                logging.error("Error: Mandatory option " + str(option) + " not set!")
                sys.exit(1)
            config.set(*option, value=defaults[option][1])

def get_config(*option):
    return defaults[option][0](*option)

def isset(option):
    try:
        if defaults[option][0](*option) == "None":
            return False
        return True
    except ValueError:
        return False

@timer.measure
def grab_screen():
    x1 = get_config('Capture','screenshot_offset_x')
    y1 = get_config('Capture','screenshot_offset_y')
    x2 = get_config('Capture','screenshot_width')
    y2 = get_config('Capture','screenshot_height')
    w, h = x2-x1, y2-y1
    size = w * h
    objlength = size * 3

    grab.getScreen.argtypes = []
    result = (ctypes.c_ubyte*objlength)()

    grab.getScreen(x1,y1, w, h, result)
    pil = Image.frombuffer('RGB', (w, h), result, 'raw', 'RGB', 0, 1)
    #draw = ImageDraw.Draw(pil)
    #draw.text((100,100), 'abcde')
    return pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)

@timer.measure
def update_workspace(workspace):
    logging.debug(f"Update workspace {workspace.num}")
    if workspace.num not in global_knowledge.keys():
        global_knowledge[workspace.num] = {
                'name': None,
                'screenshot': None,
                'windows': {}
        }

    global_knowledge[workspace.num]['name'] = workspace.name

    global_knowledge['active'] = workspace.num

def init_knowledge():
    root = i3.get_tree()
    for workspace in root.workspaces():
        update_workspace(workspace)

workspace_changed = False

def workspace_event(i3, e):
    global workspace_changed
    logging.debug(f'Workspace event at {time.time()}')
    workspace_changed = True

last_update = 0

def update_state(i3, e):
    t = timer.start("update_state")
    global last_update

    if not global_updates_running:
        return False
    if time.time() - last_update < float(args.interval if args.interval else 1):
        return False
    last_update = time.time()

    root = i3.get_tree()
    deleted = []
    for num in global_knowledge.keys():
        if type(num) is int and num not in [w.num for w in root.workspaces()]:
            deleted += [num]
    for num in deleted:
        del(global_knowledge[num])

    current_workspace = root.find_focused().workspace()
    update_workspace(current_workspace)

    t.stop()

    screenshot = grab_screen()

    if current_workspace.num == i3ipc.Connection().get_tree().find_focused().workspace().num:
        global_knowledge[current_workspace.num]['screenshot'] = screenshot


def get_hovered_frame(mpos, frames):
    for frame in frames.keys():
        if mpos[0] > frames[frame]['ul'][0] \
                and mpos[0] < frames[frame]['br'][0] \
                and mpos[1] > frames[frame]['ul'][1] \
                and mpos[1] < frames[frame]['br'][1]:
            return frame
    return None

def show_ui(source):
    global global_updates_running
    global workspace_changed

    try:
        t_init = timer.start('show_ui_init')
        t_init_cfg = timer.start('show_ui_init_cfg')

        window_width = get_config('UI', 'window_width')
        window_height = get_config('UI', 'window_height')
        
        workspaces = get_config('UI', 'workspaces')
        max_grid_x = get_config('UI', 'grid_x')
        
        padding_x = get_config('UI', 'padding_percent_x')
        padding_y = get_config('UI', 'padding_percent_y')
        spacing_x = get_config('UI', 'spacing_percent_x')
        spacing_y = get_config('UI', 'spacing_percent_y')
        frame_width = get_config('UI', 'frame_width_px')
        
        frame_active_color = get_config('UI', 'frame_active_color')
        frame_inactive_color = get_config('UI', 'frame_inactive_color')
        frame_unknown_color = get_config('UI', 'frame_unknown_color')
        frame_empty_color = get_config('UI', 'frame_empty_color')
        frame_nonexistant_color = get_config('UI', 'frame_nonexistant_color')
        
        tile_active_color = get_config('UI', 'tile_active_color')
        tile_inactive_color = get_config('UI', 'tile_inactive_color')
        tile_unknown_color = get_config('UI', 'tile_unknown_color')
        tile_empty_color = get_config('UI', 'tile_empty_color')
        tile_nonexistant_color = get_config('UI', 'tile_nonexistant_color')
        
        names_show = get_config('UI', 'names_show')
        names_font = get_config('UI', 'names_font')
        names_fontsize = get_config('UI', 'names_fontsize')
        names_color = get_config('UI', 'names_color')

        thumb_stretch = get_config('UI', 'thumb_stretch')
        highlight_percentage = get_config('UI', 'highlight_percentage')

        t_init_cfg.stop()

        t_init_display = timer.start("show_ui_init_disp")

        screen = pygame.display.set_mode((window_width, window_height), pygame.FULLSCREEN)
        pygame.display.set_caption('i3expo')

        t_init_display.stop()

        t_init_calc = timer.start("show_ui_init_calc")

        # Calculate UI dimensions
        total_x = screen.get_width()
        total_y = screen.get_height()
        logging.info(f'total_x={total_x} total_y={total_y}')

        n_workspaces = min(workspaces, len(global_knowledge) - 1)
        grid_x = min(max_grid_x, n_workspaces)
        grid_y = math.ceil(n_workspaces / max_grid_x)
        logging.info(f'grid_x={grid_x} grid_y={grid_y}')

        pad_x = round(total_x * padding_x / 100)
        pad_y = round(total_y * padding_y / 100)
        logging.info(f'pad_x={pad_x} pad_y={pad_y}')

        space_x = round(total_x * spacing_x / 100)
        space_y = round(total_y * spacing_y / 100)
        logging.info(f'space_x={space_x} space_y={space_y}')

        shot_outer_x = round((total_x - 2 * pad_x - space_x * (grid_x - 1)) / grid_x)
        shot_outer_y = round((total_y - 2 * pad_y - space_y * (grid_y - 1)) / grid_y)
        logging.info(f'shot_outer_x={shot_outer_x} shot_outer_y={shot_outer_y}')

        offset_delta_x = shot_outer_x + space_x
        offset_delta_y = shot_outer_y + space_y
        logging.info(f'offset_delta_x={offset_delta_x} offset_delta_y={offset_delta_y}')

        shot_inner_x = shot_outer_x - 2 * frame_width 
        shot_inner_y = shot_outer_y - 2 * frame_width

        pad_x = max(pad_x, (total_x - space_x * (grid_x - 1) - shot_outer_x * grid_x) / 2)
        pad_y = max(pad_y, (total_y - space_y * (grid_y - 1) - shot_outer_y * grid_y) / 2)

        t_init_calc.stop()

        t_init_missing = timer.start("show_ui_init_missing")

        screen.fill(get_config('UI', 'bgcolor'))
        
        missing_x = total_x * 0.3
        missing_y = total_y * 0.3
        missing = pygame.Surface((missing_x, missing_y), pygame.SRCALPHA, 32) 
        missing = missing.convert_alpha()
        qm = pygame.font.SysFont('sans-serif', int(missing_x * 0.5)).render('?', True, (150, 150, 150)) # RGB
        qm_size = qm.get_rect().size
        origin_x = round((missing_x - qm_size[0])/2)
        origin_y = round((missing_y - qm_size[1])/2)
        missing.blit(qm, (origin_x, origin_y))

        frames = {}

        font = pygame.font.SysFont(names_font, names_fontsize)

        t_init_missing.stop()

        t_init_frames = timer.start("show_ui_init_frame")

        print(f"Workspaces in memory: {n_workspaces}: {global_knowledge}")

        active_frame = None
        workspace_ids = [w for w in global_knowledge.keys() if w != 'active']

        for i in range(len(workspace_ids)):
            x = math.floor(i % grid_x)
            y = math.floor(i / grid_x)
            index = workspace_ids[i]

            if global_knowledge['active'] == index:
                tile_color = tile_active_color
                frame_color = frame_active_color
                image = global_knowledge[index]['screenshot']
                active_frame = index
            elif index in global_knowledge.keys() and global_knowledge[index]['screenshot']:
                tile_color = tile_inactive_color
                frame_color = frame_inactive_color
                image = global_knowledge[index]['screenshot']
            elif index in global_knowledge.keys():
                tile_color = tile_unknown_color
                frame_color = frame_unknown_color
                image = missing
            elif index <= n_workspaces:
                tile_color = tile_empty_color
                frame_color = frame_empty_color
                image = None
            else:
                tile_color = tile_nonexistant_color
                frame_color = frame_nonexistant_color
                image = None

            if not image:
                logging.info(f"Skipping workspace {index}")
                continue

            logging.debug(f"Preparing workspace {index} at {y}x{x}")

            frames[index] = {
                    'active': False,
                    'mouseoff': None,
                    'mouseon': None,
                    'ul': (None, None),
                    'br': (None, None)
            }

            origin_x = pad_x + offset_delta_x * x
            origin_y = pad_y + offset_delta_y * y

            result_x = 0
            result_y = 0
            
            if thumb_stretch:
                image = pygame.transform.smoothscale(image, (shot_inner_x, shot_inner_y))
                offset_x = 0
                offset_y = 0
            else:
                image_size = image.get_rect().size
                image_x = image_size[0]
                image_y = image_size[1]
                ratio_x = shot_inner_x / image_x
                ratio_y = shot_inner_y / image_y
                if ratio_x < ratio_y:
                    result_x = shot_inner_x
                    result_y = round(ratio_x * image_y)
                    offset_x = 0
                    offset_y = round((shot_inner_y - result_y) / 2)
                else:
                    result_x = round(ratio_y * image_x)
                    result_y = shot_inner_y
                    offset_x = round((shot_inner_x - result_x) / 2)
                    offset_y = 0
                image = pygame.transform.smoothscale(image, (result_x, result_y))

            screen.fill(frame_color,
                (
                    origin_x + offset_x,
                    origin_y + offset_y,
                    result_x + frame_width * 2,
                    result_y + frame_width * 2,
                ))

            screen.fill(tile_color,
                (
                    origin_x + frame_width + offset_x,
                    origin_y + frame_width + offset_y,
                    result_x,
                    result_y,
                ))

            screen.blit(image, (origin_x + frame_width + offset_x, origin_y + frame_width + offset_y))

            mouseoff = screen.subsurface(
                (origin_x + frame_width + offset_x, origin_y + frame_width + offset_y, result_x, result_y)
                ).copy()
            lightmask = pygame.Surface((result_x, result_y), pygame.SRCALPHA, 32)
            lightmask.convert_alpha()
            lightmask.fill((255,255,255,255 * highlight_percentage / 100))
            mouseon = mouseoff.copy()
            mouseon.blit(lightmask, (0, 0))


            frames[index]['ul'] = (
                origin_x + frame_width + offset_x,
                origin_y + frame_width + offset_y
                )
            frames[index]['br'] = (
                origin_x + frame_width + offset_x + result_x,
                origin_y + frame_width + offset_y + result_y
                )

            frames[index]['mouseon'] = mouseon.copy()
            frames[index]['mouseoff'] = mouseoff.copy()

            defined_name = False
            try:
                defined_name = config.get('Workspaces', 'workspace_' + str(index))
            except:
                pass

            if names_show and (index in global_knowledge.keys() or defined_name):
                if not defined_name:
                    name = global_knowledge[index]['name']
                else:
                    name = defined_name
                    
                name = font.render(name, True, names_color)
                name_width = name.get_rect().size[0]
                name_x = origin_x + frame_width + offset_x + round((result_x - name_width) / 2)
                name_y = origin_y + frame_width + offset_y + result_y + round(result_y * 0.05)
                screen.blit(name, (name_x, name_y))

        t_init_frames.stop()

        t_init_flip = timer.start("show_ui_init_flip")
        pygame.display.flip()
        t_init_flip.stop()

        t_init.stop()


        running = True
        use_mouse = True
        workspace_changed = False
        
        selected_id = 0
        while running:
            t_run = timer.start("show_ui_run")
            if global_updates_running:
                logging.info("Global updates is running")
                break

            if not pygame.display.get_init():
                logging.info("Display is not initialised")
                break

            if workspace_changed:
                logging.info("Workspace changed")
                break

            jump = False
            kbdmove = (0, 0)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    logging.info("Received pygame.QUIT")
                    running = False
                elif event.type == pygame.MOUSEMOTION:
                    use_mouse = True
                elif event.type == pygame.KEYDOWN:
                    use_mouse = False

                    if event.key == pygame.K_UP or event.key == pygame.K_k:
                        kbdmove = (0, -1)
                    if event.key == pygame.K_DOWN or event.key == pygame.K_j:
                        kbdmove = (0, 1)
                    if event.key == pygame.K_LEFT or event.key == pygame.K_h:
                        kbdmove = (-1, 0)
                    if event.key == pygame.K_RIGHT or event.key == pygame.K_l:
                        kbdmove = (1, 0)
                    if event.key == pygame.K_RETURN:
                        jump = True
                    if event.key == pygame.K_ESCAPE:
                        logging.info("ESCAPE key pressed")
                        running = False
                    pygame.event.clear()
                    break

                elif event.type == pygame.MOUSEBUTTONUP:
                    use_mouse = True
                    if event.button == 1:
                        jump = True
                    pygame.event.clear()
                    break

            if use_mouse:
                mpos = pygame.mouse.get_pos()
                active_frame = get_hovered_frame(mpos, frames)
            elif kbdmove != (0, 0):
                if kbdmove[0] != 0:
                    selected_id += kbdmove[0]
                elif kbdmove[1] != 0:
                    selected_id += kbdmove[1] * grid_x

                if selected_id >= n_workspaces:
                    selected_id -= n_workspaces
                elif selected_id < 0:
                    selected_id += n_workspaces

            active_frame = workspace_ids[selected_id]

            if jump:
                if active_frame in global_knowledge.keys():
                    logging.info(f'Switching to workspace {active_frame}')
                    i3.command(f'workspace number {active_frame}')
                    break

            elif not running and args.dedicated:
                logging.info(f'Exiting expo and switching to workspace {source}')
                i3.command('workspace ' + source)

            for frame in frames.keys():
                if frames[frame]['active'] and not frame == active_frame:
                    screen.blit(frames[frame]['mouseoff'], frames[frame]['ul'])
                    frames[frame]['active'] = False
            if active_frame and not frames[active_frame]['active']:
                screen.blit(frames[active_frame]['mouseon'], frames[active_frame]['ul'])
                frames[active_frame]['active'] = True

            pygame.display.update()
            pygame.time.wait(25)

            t_run.stop()
    except Exception:
        logging.exception("Failed to show UI")
    finally:
        logging.info("Closing UI")
        pygame.display.quit()
        pygame.display.init() # Allows for faster launching
        global_updates_running = True

def print_timing(name):
    if name in timer.summary:
        data = timer.summary[name]

        if not data['mean']:
            logging.warning(f"{name} timer is NaN")
        else:
            logging.info(f"{name} (x{data['samples']}): " +
                f"{data['mean'] * 1000:.4f}ms " +
                f"({data['min'] * 1000:.4f}/{data['max'] * 1000:.4f}/{data['stddev'] * 1000:.4f})")    


def main():
    try:
        read_config()
        init_knowledge()
        update_state(i3, None)

        # i3.on('workspace', workspace_event)
        i3.on('window::new', update_state)
        i3.on('window::close', update_state)
        i3.on('window::move', update_state)
        i3.on('window::floating', update_state)
        i3.on('window::fullscreen_mode', update_state)
        #i3.on('workspace', update_state)

        i3_thread = Thread(target = i3.main)
        i3_thread.daemon = True
        i3_thread.start()

        while True:
            time.sleep(1)
            update_state(i3, None)
    except SystemExit:
        pass
    except:
        logging.exception("An unknown exception has ocurred")
    finally:
        for t in timer.summary:
            print_timing(t)


if __name__ == '__main__':
    main()
