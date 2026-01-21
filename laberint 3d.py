import math
import sys
import pygame

pygame.init()

info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Raycaster + Texturas + Joystick Touch + Creador de Niveles (FIX)")
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()
FPS = 60

# =======================
# Config
# =======================
FOV = math.radians(70)
HALF_FOV = FOV / 2
NUM_RAYS = 320
MAX_DEPTH = 30.0

MOVE_SPEED = 3.2
ROT_SPEED = 2.4
DEADZONE = 0.08
EPS = 1e-6

LEVEL_FILE = "level.txt"

# =======================
# Map (puede tener filas de distinta longitud)
# =======================
WORLD_MAP = [
    "11111111111111111",
    "1000111000110001",
    "100000100010101",
    "1000010011110001",
    "1001011111010001",
    "100111000000001",
    "000111101110001",
    "1000100000001",
    "10001011000011111",
    "110010111000110011111",
    "100011100000000000001",
    "10000000001010011111",
    "1000010011110001",
    "1011011111010001",
    "100111000000001",
    "10111101110001",
    "1000100000001",
    "11001111001001111111",
    "1101111000111111",
    "1000111000110001",
    "100000100010101",
    "1000010011110001",
    "1001011111010001",
    "100111000000001",
    "10111101110001",
    "1000100000001",
    "10001011000011111",
    "100010111000110011111",
    "100011100000000000001",
    "10000010001010011111",
    "1000010011110001",
    "1011011111010001",
    "100111000000001",
    "10111101110001",
    "1000100000001",
    "111                    1111111",
]
def normalize_map(rows):
    """
    Convierte el mapa a rectangular (todas las filas mismo ancho).
    Rellena con '1' (pared) para evitar crashes por longitudes distintas.
    También fuerza bordes cerrados con '1'.
    """
    if not rows:
        return ["111", "101", "111"]

    rows = [r.strip() for r in rows if r.strip()]
    w = max(len(r) for r in rows)
    out = []
    for r in rows:
        if len(r) < w:
            r = r + ("1" * (w - len(r)))
        out.append(r)
	
    # Bordes cerrados
    top = "1" * w
    out[0] = top
    out[-1] = top
    if w >= 2:
        out = ["1" + row[1:-1] + "1" for row in out]
    else:
        out = ["1" for _ in out]

    return out

WORLD_MAP = normalize_map(WORLD_MAP)
MAP_W = len(WORLD_MAP[0])
MAP_H = len(WORLD_MAP)

def is_wall(x, y):
    mx, my = int(x), int(y)
    if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
        return True
    return WORLD_MAP[my][mx] == "1"

def find_spawn():
    for y in range(MAP_H):
        for x in range(MAP_W):
            if WORLD_MAP[y][x] == "0":
                return x + 0.5, y + 0.5
    return 1.5, 1.5

def clamp(v, a, b):
    return max(a, min(b, v))

def dz(v):
    if abs(v) < DEADZONE:
        return 0.0
    s = 1.0 if v > 0 else -1.0
    m = (abs(v) - DEADZONE) / (1.0 - DEADZONE)
    return s * clamp(m, 0.0, 1.0)

# =======================
# Textura procedural (pared)
# =======================
TEX_SIZE = 64
wall_tex = pygame.Surface((TEX_SIZE, TEX_SIZE)).convert()
for y in range(TEX_SIZE):
    for x in range(TEX_SIZE):
        brick_h = 8
        brick_w = 16
        offset = (brick_w // 2) if (y // brick_h) % 2 else 0
        bx = (x + offset) % brick_w
        by = y % brick_h
        mortar = (bx == 0) or (by == 0)
        if mortar:
            c = 35
        else:
            c = 120 + ((x * 3 + y * 5) % 40)
        wall_tex.set_at((x, y), (c, c // 2, c // 3))

# =======================
# Raycasting (DDA + tex coord)
# =======================
def cast_ray(px, py, angle):
    ray_dx = math.cos(angle)
    ray_dy = math.sin(angle)

    map_x = int(px)
    map_y = int(py)

    delta_x = abs(1.0 / (ray_dx + EPS))
    delta_y = abs(1.0 / (ray_dy + EPS))

    if ray_dx < 0:
        step_x = -1
        side_x = (px - map_x) * delta_x
    else:
        step_x = 1
        side_x = (map_x + 1.0 - px) * delta_x

    if ray_dy < 0:
        step_y = -1
        side_y = (py - map_y) * delta_y
    else:
        step_y = 1
        side_y = (map_y + 1.0 - py) * delta_y

    side = 0
    for _ in range(4096):
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
        else:
            side_y += delta_y
            map_y += step_y
            side = 1

        if map_x < 0 or map_y < 0 or map_x >= MAP_W or map_y >= MAP_H:
            break
        if WORLD_MAP[map_y][map_x] == "1":
            break

    if side == 0:
        dist = (map_x - px + (1 - step_x) / 2) / (ray_dx + EPS)
        hit = py + dist * ray_dy
        tex_u = hit - math.floor(hit)
        if ray_dx > 0:
            tex_u = 1.0 - tex_u
        shade = 0.75
    else:
        dist = (map_y - py + (1 - step_y) / 2) / (ray_dy + EPS)
        hit = px + dist * ray_dx
        tex_u = hit - math.floor(hit)
        if ray_dy < 0:
            tex_u = 1.0 - tex_u
        shade = 1.0

    dist = max(0.01, min(MAX_DEPTH, dist))
    return dist, shade, tex_u

# =======================
# Joystick touch (UNO) - X gira, Y mueve
# Compatible con FINGER y MOUSE
# =======================
JOY_R = int(min(WIDTH, HEIGHT) * 0.25)
JOY_CENTER = [JOY_R + 60, HEIGHT - JOY_R - 60]
joy_knob = JOY_CENTER.copy()
joy_val = [0.0, 0.0]
touch_active = False
LEFT_HALF = pygame.Rect(0, 0, WIDTH // 2, HEIGHT)

def set_knob_from_pos(x, y):
    vx = x - JOY_CENTER[0]
    vy = y - JOY_CENTER[1]
    d = math.hypot(vx, vy)
    if d > JOY_R:
        vx = vx / d * JOY_R
        vy = vy / d * JOY_R

    joy_knob[0] = JOY_CENTER[0] + vx
    joy_knob[1] = JOY_CENTER[1] + vy

    joy_val[0] = dz(vx / JOY_R)   # X = girar
    joy_val[1] = dz(vy / JOY_R)   # Y = mover

def reset_joystick():
    joy_knob[0], joy_knob[1] = JOY_CENTER[0], JOY_CENTER[1]
    joy_val[0], joy_val[1] = 0.0, 0.0

def draw_joystick():
    pygame.draw.circle(screen, (255, 255, 255), (int(JOY_CENTER[0]), int(JOY_CENTER[1])), JOY_R, 2)
    pygame.draw.circle(screen, (255, 255, 255), (int(joy_knob[0]), int(joy_knob[1])), JOY_R // 2, 2)

# =======================
# Editor de niveles (FIX: layout adaptable + 2 dedos)
# =======================
font = pygame.font.SysFont(None, 26)
edit_mode = False
status_msg = ""
status_timer = 0.0

fingers_down = set()  # para detectar 2 dedos

GRID_PAD = 12
BTN_H = 44
BTN_W = 160
BTN_GAP = 10
EDITOR_MARGIN_BOTTOM = 110  # espacio para botones + texto

def set_status(text, seconds=1.6):
    global status_msg, status_timer
    status_msg = text
    status_timer = seconds

def compute_editor_layout():
    """
    Devuelve: grid_scale, grid_rect, btn_edit, btn_save, btn_load, help_pos
    Garantiza que el grid y botones queden dentro de pantalla.
    """
    max_w = int(WIDTH * 0.55)              # editor ocupa ~mitad izquierda
    max_h = HEIGHT - EDITOR_MARGIN_BOTTOM  # deja espacio para botones/texto

    if MAP_W <= 0 or MAP_H <= 0:
        scale = 20
    else:
        scale_w = max(10, max_w // MAP_W)
        scale_h = max(10, max_h // MAP_H)
        scale = max(10, min(scale_w, scale_h))

    grid_w = MAP_W * scale
    grid_h = MAP_H * scale
    grid_rect = pygame.Rect(GRID_PAD, GRID_PAD, grid_w, grid_h)

    # Botones: por defecto debajo del grid
    btn_y = grid_rect.bottom + 12
    btn_edit = pygame.Rect(GRID_PAD, btn_y, BTN_W, BTN_H)
    btn_save = pygame.Rect(GRID_PAD + BTN_W + BTN_GAP, btn_y, BTN_W, BTN_H)
    btn_load = pygame.Rect(GRID_PAD + (BTN_W + BTN_GAP) * 2, btn_y, BTN_W, BTN_H)

    # Si no entran, los ponemos en columna arriba-derecha
    if (btn_load.right > WIDTH - GRID_PAD) or (btn_y + BTN_H > HEIGHT - GRID_PAD):
        top_y = GRID_PAD
        right_x = WIDTH - GRID_PAD - BTN_W
        btn_edit = pygame.Rect(right_x, top_y, BTN_W, BTN_H)
        btn_save = pygame.Rect(right_x, top_y + BTN_H + BTN_GAP, BTN_W, BTN_H)
        btn_load = pygame.Rect(right_x, top_y + (BTN_H + BTN_GAP) * 2, BTN_W, BTN_H)
        help_pos = (GRID_PAD, grid_rect.bottom + 12)
    else:
        help_pos = (GRID_PAD, btn_edit.bottom + 10)

    return scale, grid_rect, btn_edit, btn_save, btn_load, help_pos

def draw_button(rect, label, active=False):
    col = (70, 70, 90) if not active else (110, 110, 150)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    pygame.draw.rect(screen, (220, 220, 220), rect, 2, border_radius=10)
    t = font.render(label, True, (240, 240, 240))
    screen.blit(t, (rect.x + (rect.w - t.get_width()) // 2,
                    rect.y + (rect.h - t.get_height()) // 2))

def grid_cell_from_screen(x, y, grid_rect, grid_scale):
    if not grid_rect.collidepoint(x, y):
        return None
    gx = (x - grid_rect.x) // grid_scale
    gy = (y - grid_rect.y) // grid_scale
    if 0 <= gx < MAP_W and 0 <= gy < MAP_H:
        return int(gx), int(gy)
    return None

def set_cell(gx, gy, val_char):
    global WORLD_MAP
    row = WORLD_MAP[gy]
    if row[gx] == val_char:
        return
    WORLD_MAP = WORLD_MAP[:]
    WORLD_MAP[gy] = row[:gx] + val_char + row[gx + 1:]

def toggle_cell(gx, gy):
    # no abrir bordes
    if gx == 0 or gy == 0 or gx == MAP_W - 1 or gy == MAP_H - 1:
        return
    set_cell(gx, gy, "0" if WORLD_MAP[gy][gx] == "1" else "1")

def save_level(path=LEVEL_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            for row in WORLD_MAP:
                f.write(row + "\n")
        set_status(f"Guardado: {path}")
    except Exception as ex:
        set_status(f"Error guardando: {ex}", 2.2)

def load_level(path=LEVEL_FILE):
    global WORLD_MAP, MAP_W, MAP_H, px, py
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = [line.strip() for line in f.readlines() if line.strip()]
        WORLD_MAP = normalize_map(rows)
        MAP_W = len(WORLD_MAP[0])
        MAP_H = len(WORLD_MAP)
        px, py = find_spawn()
        set_status(f"Cargado: {path}")
    except FileNotFoundError:
        set_status("No existe level.txt (primero guardá)", 2.0)
    except Exception as ex:
        set_status(f"Error cargando: {ex}", 2.2)

def draw_editor_overlay(player_x, player_y):
    grid_scale, grid_rect, btn_edit, btn_save, btn_load, help_pos = compute_editor_layout()

    # oscurece fondo
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    screen.blit(overlay, (0, 0))

    # grilla
    for gy in range(MAP_H):
        for gx in range(MAP_W):
            cell = WORLD_MAP[gy][gx]
            r = pygame.Rect(grid_rect.x + gx * grid_scale,
                            grid_rect.y + gy * grid_scale,
                            grid_scale, grid_scale)
            if cell == "1":
                pygame.draw.rect(screen, (200, 200, 220), r)
            else:
                pygame.draw.rect(screen, (40, 40, 55), r)
            pygame.draw.rect(screen, (20, 20, 30), r, 1)

    # jugador
    pgx, pgy = int(player_x), int(player_y)
    if 0 <= pgx < MAP_W and 0 <= pgy < MAP_H:
        pr = pygame.Rect(grid_rect.x + pgx * grid_scale,
                         grid_rect.y + pgy * grid_scale,
                         grid_scale, grid_scale)
        pygame.draw.rect(screen, (255, 120, 120), pr, 3)

    # ayuda
    t1 = font.render("Editor: tocá celdas para poner/quitar paredes", True, (240, 240, 240))
    t2 = font.render("Atajo: 2 dedos = abrir/cerrar editor", True, (240, 240, 240))
    screen.blit(t1, help_pos)
    screen.blit(t2, (help_pos[0], help_pos[1] + 26))

    return grid_scale, grid_rect, btn_edit, btn_save, btn_load

# =======================
# Player
# =======================
px, py = find_spawn()   # spawn seguro (NO adentro de pared)
pa = 0.0

running = True
while running:
    dt = clock.tick(FPS) / 1000.0

    if status_timer > 0:
        status_timer -= dt
        if status_timer <= 0:
            status_msg = ""

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                running = False
            if e.key == pygame.K_e:
                edit_mode = not edit_mode
                set_status("Editor ON" if edit_mode else "Editor OFF")
                touch_active = False
                reset_joystick()
            if e.key == pygame.K_s:
                save_level()
            if e.key == pygame.K_l:
                load_level()

        # ---- Touch FINGER: 2 dedos para toggle editor ----
        if e.type == pygame.FINGERDOWN:
            fingers_down.add(e.finger_id)
            if len(fingers_down) >= 2:
                edit_mode = not edit_mode
                set_status("Editor ON" if edit_mode else "Editor OFF")
                touch_active = False
                reset_joystick()
                # no hagas nada más con este evento (evita activar joystick)
                continue

            x = int(e.x * WIDTH)
            y = int(e.y * HEIGHT)

            # Si editor: interactuar con UI / grid
            if edit_mode:
                grid_scale, grid_rect, btn_edit, btn_save, btn_load = draw_editor_overlay(px, py)

                if btn_edit.collidepoint(x, y):
                    edit_mode = False
                    set_status("Editor OFF")
                elif btn_save.collidepoint(x, y):
                    save_level()
                elif btn_load.collidepoint(x, y):
                    load_level()
                else:
                    cell = grid_cell_from_screen(x, y, grid_rect, grid_scale)
                    if cell:
                        gx, gy = cell
                        toggle_cell(gx, gy)
                        if is_wall(px, py):
                            px, py = find_spawn()
                continue

            # Si juego: joystick (mitad izquierda)
            if LEFT_HALF.collidepoint(x, y):
                touch_active = True
                JOY_CENTER[0], JOY_CENTER[1] = x, y
                set_knob_from_pos(x, y)

        if e.type == pygame.FINGERMOTION and touch_active and (not edit_mode):
            x = int(e.x * WIDTH)
            y = int(e.y * HEIGHT)
            set_knob_from_pos(x, y)

        if e.type == pygame.FINGERUP:
            fingers_down.discard(e.finger_id)
            if touch_active:
                touch_active = False
                reset_joystick()

        # ---- Mouse fallback (algunos Android) ----
        if e.type == pygame.MOUSEBUTTONDOWN:
            x, y = e.pos

            if edit_mode:
                grid_scale, grid_rect, btn_edit, btn_save, btn_load = draw_editor_overlay(px, py)

                if btn_edit.collidepoint(x, y):
                    edit_mode = False
                    set_status("Editor OFF")
                elif btn_save.collidepoint(x, y):
                    save_level()
                elif btn_load.collidepoint(x, y):
                    load_level()
                else:
                    cell = grid_cell_from_screen(x, y, grid_rect, grid_scale)
                    if cell:
                        gx, gy = cell
                        toggle_cell(gx, gy)
                        if is_wall(px, py):
                            px, py = find_spawn()
                continue

            if LEFT_HALF.collidepoint(x, y):
                touch_active = True
                JOY_CENTER[0], JOY_CENTER[1] = x, y
                set_knob_from_pos(x, y)

        if e.type == pygame.MOUSEMOTION and touch_active and (not edit_mode):
            x, y = e.pos
            set_knob_from_pos(x, y)

        if e.type == pygame.MOUSEBUTTONUP and touch_active:
            touch_active = False
            reset_joystick()

    # =======================
    # Movimiento (solo en modo juego)
    # =======================
    if not edit_mode:
        turn = joy_val[0]
        move = -joy_val[1]  # arriba=adelante

        pa = (pa + turn * ROT_SPEED * dt) % math.tau

        dx = math.cos(pa)
        dy = math.sin(pa)

        nx = px + dx * move * MOVE_SPEED * dt
        ny = py + dy * move * MOVE_SPEED * dt

        if not is_wall(nx, py): px = nx
        if not is_wall(px, ny): py = ny

    # =======================
    # Render 3D
    # =======================
    screen.fill((0, 0, 0))
    pygame.draw.rect(screen, (35, 35, 55), (0, 0, WIDTH, HEIGHT // 2))
    pygame.draw.rect(screen, (25, 22, 18), (0, HEIGHT // 2, WIDTH, HEIGHT // 2))

    start_angle = pa - HALF_FOV
    ray_step = FOV / NUM_RAYS
    col_w = (WIDTH / NUM_RAYS)

    for i in range(NUM_RAYS):
        angle = start_angle + i * ray_step
        dist, shade, tex_u = cast_ray(px, py, angle)
        dist *= math.cos(pa - angle)  # fish-eye correction

        wall_h = int((HEIGHT * 0.9) / max(0.01, dist))
        wall_h = min(HEIGHT, wall_h)

        x = int(i * col_w)
        w = int(col_w) + 1
        y0 = (HEIGHT // 2) - (wall_h // 2)

        tex_x = int(tex_u * (TEX_SIZE - 1))
        tex_x = int(clamp(tex_x, 0, TEX_SIZE - 1))

        column = wall_tex.subsurface((tex_x, 0, 1, TEX_SIZE))
        column_scaled = pygame.transform.scale(column, (w, wall_h))

        fog = clamp(1.0 - (dist / MAX_DEPTH), 0.15, 1.0)
        intensity = fog * shade
        mult = int(255 * intensity)

        img = column_scaled.copy()
        img.fill((mult, mult, mult), special_flags=pygame.BLEND_RGB_MULT)
        screen.blit(img, (x, y0))

    # UI
    if edit_mode:
        draw_editor_overlay(px, py)
    else:
        draw_joystick()
        # tip rápido
        tip = font.render("2 dedos = Editor | Arriba/abajo mueve | Izq/der gira", True, (220, 220, 220))
        screen.blit(tip, (16, 16))

    if status_msg:
        s = font.render(status_msg, True, (255, 255, 255))
        screen.blit(s, (WIDTH - s.get_width() - 16, 16))

    pygame.display.flip()

pygame.quit()
sys.exit()