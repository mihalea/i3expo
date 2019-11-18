#!/usr/bin/env python3

from xdg.BaseDirectory import xdg_config_home
from PIL import Image, ImageDraw
from threading import Thread
from i3expo.debounce import Debounce
from i3expo.geometry import Geometry, Dimension

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import logging
import math
import argparse
import time
import traceback
import sys
import signal
import copy
import i3ipc
import pygame
import ctypes
import configparser

global_updates_running = True
global_knowledge = {'active': -1}

i3 = i3ipc.Connection()

screenshot_lib = '/usr/share/i3expo/prtscn.so'
grab = ctypes.CDLL(screenshot_lib)

parser = argparse.ArgumentParser(
    description="Display an overview of all open workspaces")
parser.add_argument("-v", "--verbose",
                    help="Print more program data", action='store_true')
parser.add_argument("-i", "--interval",
                    help="Update interval in seconds (default: 1s)")
parser.add_argument("-d", "--dedicated",
                    help="Launch on a dedicated workspace", action="store_true")
args = parser.parse_args()

loop_interval = 100.0
config = None
config_path = os.path.join(xdg_config_home, "i3expo", "config")
update_debounced = None


def signal_quit(signal, frame):
    logging.info("Shutting down...")
    pygame.display.quit()
    pygame.quit()
    i3.main_quit()
    sys.exit(0)


def signal_reload(signal, frame):
    global loop_interval

    logging.info("Reloading config")
    read_config()

    loop_interval = config.getfloat('Daemon', 'forced_update_interval')


def signal_show(signal, frame):
    global global_updates_running

    logging.info("Showing UI")
    if not global_updates_running:
        global_updates_running = True
    elif should_show_ui():
        global_updates_running = False
        update_debounced.reset()

        source = i3.get_tree().find_focused().workspace().name
        if args.dedicated:
            i3.command('workspace i3expod-temporary-workspace')

        ui_thread = Thread(target=show_ui, args=[source])
        ui_thread.daemon = True
        ui_thread.start()


def should_show_ui():
    return len(global_knowledge) - 1 > 1


def get_color(raw):
    return pygame.Color(raw)


def read_config():
    global config

    converters = {'color': get_color}

    pygame.display.init()
    disp_info = pygame.display.Info()

    defaults = {
        'Capture': {
            'screenshot_width': disp_info.current_w,
            'screenshot_height': disp_info.current_h,
            'screenshot_offset_x': 0,
            'screenshot_offset_y': 0,
            'screenshot_delay': 0.2
        },
        'UI': {
            'window_width': disp_info.current_w,
            'window_height': disp_info.current_h,
            'bgcolor': 'gray20',
            'frame_active_color': '#5a6da4',
            'frame_inactive_color': '#93afb3',
            'frame_missing_color': '#ffe6d0',
            'tile_missing_color': 'gray40',

            'grid_x': 3,
            'workspaces': 9,

            'padding_percent_x': 5,
            'padding_percent_y': 5,
            'spacing_percent_x': 4,
            'spacing_percent_y': 4,
            'frame_width_px': 3,

            'names_show': True,
            'names_font': 'verdana',  # list with pygame.font.get_fonts()
            'names_fontsize': 25,
            'names_color': 'white',
            'highlight_percentage': 20
        },
        'Daemon': {
            'forced_update_interval': 10.0,
            'debounce_period': 1.0,
        }
    }
    pygame.display.quit()

    config = configparser.ConfigParser(
        converters=converters
    )

    config.read_dict(defaults)


    root_dir = os.path.dirname(config_path)
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)

    if os.path.exists(config_path):
        config.read(config_path)
    else:
        with open(config_path, 'w') as f:
            config.write(f)

def grab_screen():
    logging.debug("Grabbing screen")
    x1 = config.getint('Capture', 'screenshot_offset_x')
    y1 = config.getint('Capture', 'screenshot_offset_y')
    x2 = config.getint('Capture', 'screenshot_width')
    y2 = config.getint('Capture', 'screenshot_height')
    w, h = x2-x1, y2-y1
    size = w * h
    objlength = size * 3

    grab.getScreen.argtypes = []
    result = (ctypes.c_ubyte*objlength)()
    grab.getScreen(x1, y1, w, h, result)
    return (w, h, result)


def process_image(raw_img):
    pil = Image.frombuffer(
        'RGB', (raw_img[0], raw_img[1]), raw_img[2], 'raw', 'RGB', 0, 1)
    return pygame.image.fromstring(pil.tobytes(), pil.size, pil.mode)


def update_workspace(workspace):
    # logging.debug("Update workspace %s", workspace.num)
    if workspace.num not in global_knowledge.keys():
        global_knowledge[workspace.num] = {
            'name': None,
            'screenshot': None,
            'windows': {},
            'last_update': 0,
            'state': 0
        }

    global_knowledge[workspace.num]['name'] = workspace.name
    global_knowledge['active'] = workspace.num


def init_knowledge():
    for workspace in i3.get_tree().workspaces():
        update_workspace(workspace)


def on_workspace(i3, e):
    global global_updates_running, loop_interval

    # global_updates_running = True
    update_state(i3, rate_limit_period=loop_interval, force=True)

def tree_hash(workspace):
    state = 0
    for con in workspace.leaves():
        f = 31 if con.focused else 0  # so focus change can be detected
        state += con.id % (con.rect.x + con.rect.y + con.rect.width + con.rect.height + f)

    logging.debug("Tree hash for workspace %s: %s", workspace.num, state)
    return state

def tree_has_changed(workspace):
    state = tree_hash(workspace)

    if global_knowledge[workspace.num]['state'] == state:
        return False
    else:
        global_knowledge[workspace.num]['state'] = state
        return True


def should_update(rate_limit_period, current_workspace, force):
    if not global_updates_running:
        return False
    elif rate_limit_period is not None and time.time() - global_knowledge[current_workspace.num]['last_update'] <= rate_limit_period:
        return False
    elif force:
        update_debounced.reset()
        tree_has_changed(current_workspace)
        return True
    elif not tree_has_changed(current_workspace):
        return False

    return True


def update_state(i3, e=None, rate_limit_period=None, force=False):
    # Prevent screenshoft from being takes too fast and capturing
    # the still unchanged workspace instead of the new one
    time.sleep(config.getfloat('Capture', 'screenshot_delay'))

    global last_update

    root = i3.get_tree()
    current_workspace = root.find_focused().workspace()

    update_workspace(current_workspace)
    if should_update(rate_limit_period, current_workspace, force):
        logging.debug("Update state for workspace %s", current_workspace.num)
        
        workspaces = [w.num for w in root.workspaces()]
        deleted = []
        for num in global_knowledge:
            if type(num) is int and num not in workspaces:
                deleted.append(num)
        for num in deleted:
            del global_knowledge[num]

        global_knowledge[current_workspace.num]['screenshot'] = grab_screen()
        global_knowledge[current_workspace.num]['last_update'] = time.time()


def get_hovered_frame(mpos, frames):
    for frame in frames:
        if mpos[0] > frame['ul'].x \
                and mpos[0] < frame['br'].x \
                and mpos[1] > frame['ul'].y \
                and mpos[1] < frame['br'].y:
            return frame['ws_num']
    return None


def show_ui(source):
    global global_updates_running

    try:
        window_width = config.getint('UI', 'window_width')
        window_height = config.getint('UI', 'window_height')

        pygame.display.init()
        pygame.font.init()
        screen = pygame.display.set_mode(
            (window_width, window_height), pygame.FULLSCREEN)
        pygame.display.set_caption('i3expo')

        geometry = init_geometry(screen)
        tiles = init_tiles(screen)
        draw_tiles(screen, tiles, geometry)

        pygame.display.flip()
        input_loop(screen, source, tiles, geometry.grid.x)
    except Exception:
        logging.exception("Failed to show UI")
    finally:
        logging.info("Closing UI")
        pygame.display.quit()
        pygame.display.init()  # Allows for faster launching
        global_updates_running = True


def input_loop(screen, source, tiles, columns):
    running = True
    use_mouse = True

    selected_id = 0
    while running:
        if global_updates_running:
            logging.info("Global updates is running")
            break

        if not pygame.display.get_init():
            logging.info("Display is not initialised")
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
                    logging.debug("ESCAPE key pressed")
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
            active_frame = get_hovered_frame(mpos, tiles)
            logging.debug("Mouse selected: %s", active_frame)
        elif kbdmove != (0, 0):
            if kbdmove[0] != 0:
                selected_id += kbdmove[0]
            elif kbdmove[1] != 0:
                selected_id += kbdmove[1] * columns

            if selected_id >= len(tiles):
                selected_id -= len(tiles)
            elif selected_id < 0:
                selected_id += len(tiles)

            active_frame = tiles[selected_id]['ws_num']
            logging.debug("Keyboard selected: %s", active_frame)


        if jump:
            if active_frame in global_knowledge.keys():
                logging.info('Switching to workspace %s', active_frame)
                i3.command(f'workspace number {active_frame}')
                break

        elif not running and args.dedicated:
            logging.info('Exiting expo and switching to workspace %s', source)
            i3.command('workspace ' + source)

        for tile in tiles:
            if tile['active'] and not tile['ws_num'] == active_frame:
                screen.blit(tile['mouseoff'], (tile['ul'].x, tile['ul'].y))
                tile['active'] = False

            if not tile['active'] and tile['ws_num'] == active_frame:
                screen.blit(tile['mouseon'], (tile['ul'].x, tile['ul'].y))
                tile['active'] = True

        pygame.display.update()
        pygame.time.wait(25)


def init_geometry(screen):
    g = Geometry()

    workspaces = config.getint('UI', 'workspaces')
    max_grid_x = config.getint('UI', 'grid_x')

    padding_x = config.getint('UI', 'padding_percent_x')
    padding_y = config.getint('UI', 'padding_percent_y')
    spacing_x = config.getint('UI', 'spacing_percent_x')
    spacing_y = config.getint('UI', 'spacing_percent_y')
    frame_width = config.getint('UI', 'frame_width_px')

    g.total.x = screen.get_width()
    g.total.y = screen.get_height()
    logging.debug('total_x=%s total_y=%s', g.total.x, g.total.y)

    n_workspaces = min(workspaces, len(global_knowledge) - 1)

    g.grid.x = min(max_grid_x, n_workspaces)
    g.grid.y = math.ceil(n_workspaces / max_grid_x)
    logging.debug('grid_x=%s grid_y=%s', g.grid.x, g.grid.y)

    g.pad.x = round(g.total.x * padding_x / 100)
    g.pad.y = round(g.total.y * padding_y / 100)
    logging.debug('pad_x=%s pad_y=%s', g.pad.x, g.pad.y)

    g.space.x = round(g.total.x * spacing_x / 100)
    g.space.y = round(g.total.y * spacing_y / 100)
    logging.debug('space_x=%s space_y=%s', g.space.x, g.space.y)

    g.outer.x = round(
        (g.total.x - 2 * g.pad.x - g.space.x * (g.grid.x - 1)) / g.grid.x)
    g.outer.y = round(
        (g.total.y - 2 * g.pad.y - g.space.y * (g.grid.y - 1)) / g.grid.y)
    logging.debug('shot_outer_x=%s shot_outer_y=%s', g.outer.x, g.outer.y)

    g.offset.x = g.outer.x + g.space.x
    g.offset.y = g.outer.y + g.space.y
    logging.debug('offset_delta_x=%s offset_delta_y=%s',
                  g.offset.x, g.offset.y)

    g.inner.x = g.outer.x - 2 * frame_width
    g.inner.y = g.outer.y - 2 * frame_width

    g.pad.x = max(g.pad.x, (g.total.x - g.space.x *
                            (g.grid.x - 1) - g.outer.x * g.grid.x) / 2)
    g.pad.y = max(g.pad.y, (g.total.y - g.space.y *
                            (g.grid.y - 1) - g.outer.y * g.grid.y) / 2)

    g.frame = frame_width

    return g


def autosize_image(g, image):
    result = Dimension()
    offset = Dimension()

    image_size = image.get_rect().size
    image_dim = Dimension(image_size[0], image_size[1])
    ratio = g.inner / image_dim
    if ratio.x < ratio.y:
        result.set(g.inner.x, round(ratio.x * image_dim.y))
        offset.set(0, round((g.inner.y - result.y) / 2))
    else:
        result.set(round(ratio.y * image_dim.x), g.inner.y)
        offset.set(round((g.inner.x - result.x) / 2), 0)

    resized = pygame.transform.smoothscale(image, (result.x, result.y))

    return (resized, result, offset)


def draw_tiles(screen, tiles, g):
    highlight_percentage = config.getint('UI', 'highlight_percentage')
    bgcolor = config.getcolor('UI', 'bgcolor')

    screen.fill(bgcolor)

    for idx, t in enumerate(tiles):
        x = math.floor(idx % g.grid.x)
        y = math.floor(idx / g.grid.x)

        origin = Dimension(
            g.pad.x + g.offset.x * x,
            g.pad.y + g.offset.y * y
        )
        result = Dimension()
        offset = Dimension()

        if t['screenshot']:
            t['img'] = process_image(t['screenshot'])

        (image, result, offset) = autosize_image(g, t['img'])
        t['ul'] = origin + g.frame + offset
        t['br'] = origin + g.frame + offset + result

        screen.fill(t['frame'],
                    (
                        origin.x + offset.x,
                        origin.y + offset.y,
                        result.x + g.frame * 2,
                        result.y + g.frame * 2,
        ))

        if t['tile']:
            screen.fill(t['tile'],
                        (
                            origin.x + g.frame + offset.x,
                            origin.y + g.frame + offset.y,
                            result.x,
                            result.y,
            ))

        screen.blit(image, (origin.x + g.frame + offset.x,
                            origin.y + g.frame + offset.y))

        mouseoff = screen.subsurface(
            (origin.x + g.frame + offset.x, origin.y +
             g.frame + offset.y, result.x, result.y)
        ).copy()
        lightmask = pygame.Surface((result.x, result.y), pygame.SRCALPHA, 32)
        lightmask.convert_alpha()
        lightmask.fill((255, 255, 255, 255 * highlight_percentage / 100))
        mouseon = mouseoff.copy()
        mouseon.blit(lightmask, (0, 0))

        t['mouseon'] = mouseon.copy()
        t['mouseoff'] = mouseoff.copy()

        draw_name(screen, t['ws_num'], origin, offset, result, g.frame)


def init_tiles(screen):
    logging.debug("Workspace data: %s", global_knowledge)

    frame_active_color = config.getcolor('UI', 'frame_active_color')
    frame_inactive_color = config.getcolor('UI', 'frame_inactive_color')
    frame_missing_color = config.getcolor('UI', 'frame_missing_color')
    tile_missing_color = config.getcolor('UI', 'tile_missing_color')

    missing_tile = draw_missing_tile(screen)

    workspace_ids = [w for w in global_knowledge if w != 'active']

    tiles = []
    for i in range(len(workspace_ids)):
        index = workspace_ids[i]

        t = {
            'active': False,
            'mouseoff': None,
            'mouseon': None,
            'ul': None,
            'br': None,
            'frame': None,
            'tile': None,
            'screenshot': None,
            'ws_num': index
        }

        if global_knowledge[index]['screenshot'] != None:
            t['screenshot'] = global_knowledge[index]['screenshot']
            if global_knowledge['active'] == index:
                t['frame'] = frame_active_color
            else:
                t['frame'] = frame_inactive_color
        else:
            t['tile'] = tile_missing_color
            t['frame'] = frame_missing_color
            t['img'] = missing_tile

        tiles.append(t)

    return sorted(tiles, key=lambda k: k['ws_num'])


def draw_name(screen, index, origin, offset, result, frame):
    names_show = config.get('UI', 'names_show')
    names_font = config.get('UI', 'names_font')
    names_fontsize = config.getint('UI', 'names_fontsize')
    names_color = config.getcolor('UI', 'names_color')

    defined_name = False
    try:
        defined_name = config.get('Workspaces', f'workspace_{index}')
    except:
        pass

    if names_show and (index in global_knowledge.keys() or defined_name):
        if not defined_name:
            name = global_knowledge[index]['name']
        else:
            name = defined_name

        font = pygame.font.SysFont(names_font, names_fontsize)

        name = font.render(name, True, names_color)
        name_width = name.get_rect().size[0]
        screen.blit(name, (
            origin.x + frame + offset.x +
            round((result.x - name_width) / 2),
            origin.y + frame + offset.y +
            result.y + round(result.y * 0.05)
        ))


def draw_missing_tile(screen):
    missing_x = screen.get_width() * 0.3
    missing_y = screen.get_height() * 0.3

    missing = pygame.Surface((missing_x, missing_y), pygame.SRCALPHA, 32)
    missing = missing.convert_alpha()
    qm = pygame.font.SysFont(
        'sans-serif', int(missing_x * 0.5)).render('?', True, (150, 150, 150))  # RGB
    qm_size = qm.get_rect().size
    origin_x = round((missing_x - qm_size[0])/2)
    origin_y = round((missing_y - qm_size[1])/2)
    missing.blit(qm, (origin_x, origin_y))

    return missing

def save_pid():
    pid = os.getpid()
    uid = os.getuid()
    logging.info("Registering process PID=%s", pid)
    with open(f"/var/run/user/{uid}/i3expo.pid", "w") as f:
        f.write(f"{pid}")


def setup_logging():
    logLevel = logging.INFO
    if args.verbose:
        logLevel = logging.DEBUG

    logging.basicConfig(
        format='[%(levelname)s] %(asctime)s: %(message)s', level=logLevel)


def main():
    global update_debounced
    try:
        setup_logging()
        save_pid()

        signal.signal(signal.SIGINT, signal_quit)
        signal.signal(signal.SIGTERM, signal_quit)
        signal.signal(signal.SIGHUP, signal_reload)
        signal.signal(signal.SIGUSR1, signal_show)

        read_config()

        update_debounced = Debounce(config.getfloat(
            'Daemon', 'debounce_period'), update_state)

        init_knowledge()
        update_state(i3, force=True)

        # i3.on('workspace', workspace_event)
        # i3.on('window::new', update_debounced)
        # i3.on('window::close', update_debounced)
        i3.on('window::move', update_debounced)
        i3.on('window::floating', update_debounced)
        i3.on('window::fullscreen_mode', update_debounced)
        i3.on('window::focus', update_debounced)
        i3.on('workspace', on_workspace)

        logging.info("Starting main threads")

        i3_thread = Thread(target=i3.main)
        i3_thread.daemon = True
        i3_thread.start()

        loop_interval = config.getfloat('Daemon', 'forced_update_interval')
        while True:
            time.sleep(loop_interval)
            update_state(i3, rate_limit_period=loop_interval, force=True)
    except SystemExit:
        pass
    except:
        logging.exception("An unknown exception has ocurred")


if __name__ == '__main__':
    main()
