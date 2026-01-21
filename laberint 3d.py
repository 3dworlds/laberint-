import math
import sys
import pygame
import random

pygame.init()

# =========================================================
# Pantalla real (fullscreen) + render interno (más rápido)
# =========================================================
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
info = pygame.display.Info()
SCREEN_W, SCREEN_H = info.current_w, info.current_h
pygame.display.set_caption("Raycaster DOOM-lite + Touch WASD + Look Right Half + Fire")
pygame.mouse.set_visible(False)

# Render interno (16:9) para ganar FPS
BASE_W, BASE_H = 960, 540  # si va lento: 800x450
base = pygame.Surface((BASE_W, BASE_H))

scale = min(SCREEN_W / BASE_W, SCREEN_H / BASE_H)
FINAL_W, FINAL_H = int(BASE_W * scale), int(BASE_H * scale)
OFF_X = (SCREEN_W - FINAL_W) // 2
OFF_Y = (SCREEN_H - FINAL_H) // 2

clock = pygame.time.Clock()
FPS = 60

# =========================================================
# CONFIG
# =========================================================
FOV = math.radians(70)
HALF_FOV = FOV / 2

NUM_RAYS = 320
MAX_DEPTH = 30.0
EPS = 1e-6

MOVE_SPEED = 3.4
MOUSE_SENS = 0.0032

DEADZONE = 0.08

# =========================================================
# MAP (se normaliza a rectangular)
# =========================================================
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
    if not rows:
        return ["111", "101", "111"]
    rows = [r.rstrip("\n") for r in rows if r.strip()]
    w = max(len(r) for r in rows)
    out = []
    for r in rows:
        if len(r) < w:
            r = r + ("1" * (w - len(r)))
        out.append(r)
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

def ang_wrap(a):
    while a > math.pi: a -= 2*math.pi
    while a < -math.pi: a += 2*math.pi
    return a

# =========================================================
# Textura procedural (pared) + columnas pre-calc
# =========================================================
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

TEX_COLS = [wall_tex.subsurface((x, 0, 1, TEX_SIZE)).copy() for x in range(TEX_SIZE)]

# =========================================================
# Raycasting
# =========================================================
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

# =========================================================
# INPUT mapping: pantalla real -> base
# =========================================================
def screen_to_base(sx, sy):
    bx = (sx - OFF_X) / scale
    by = (sy - OFF_Y) / scale
    inside = (0 <= bx < BASE_W) and (0 <= by < BASE_H)
    return int(bx), int(by), inside

# =========================================================
# UI
# =========================================================
ui_font = pygame.font.SysFont(None, 22)

def draw_crosshair(surf):
    cx, cy = BASE_W//2, BASE_H//2
    pygame.draw.line(surf, (255,255,255), (cx-8, cy), (cx+8, cy), 1)
    pygame.draw.line(surf, (255,255,255), (cx, cy-8), (cx, cy+8), 1)

# =========================================================
# JOYSTICK MOVIMIENTO (WASD COMPLETO)
#   joy_move_x = strafe (A/D)
#   joy_move_y = forward/back (W/S)
# =========================================================
JOY_R = int(min(BASE_W, BASE_H) * 0.23)
JOY_CENTER = [JOY_R + 40, BASE_H - JOY_R - 40]
joy_knob = JOY_CENTER.copy()
joy_move_x = 0.0
joy_move_y = 0.0
touch_move_active = False
move_touch_id = None

LEFT_HALF = pygame.Rect(0, 0, BASE_W // 2, BASE_H)

def set_joy_from_pos(x, y):
    global joy_move_x, joy_move_y
    vx = x - JOY_CENTER[0]
    vy = y - JOY_CENTER[1]
    d = math.hypot(vx, vy)
    if d > JOY_R:
        vx = vx / d * JOY_R
        vy = vy / d * JOY_R

    joy_knob[0] = JOY_CENTER[0] + vx
    joy_knob[1] = JOY_CENTER[1] + vy

    joy_move_x = dz(vx / JOY_R)    # A/D
    joy_move_y = dz(vy / JOY_R)    # arriba negativo -> W
    joy_move_y = -joy_move_y       # invertimos para que arriba sea +forward

def reset_joystick():
    global joy_move_x, joy_move_y
    joy_knob[0], joy_knob[1] = JOY_CENTER[0], JOY_CENTER[1]
    joy_move_x, joy_move_y = 0.0, 0.0

def draw_joystick(surf):
    pygame.draw.circle(surf, (255,255,255), (int(JOY_CENTER[0]), int(JOY_CENTER[1])), JOY_R, 2)
    pygame.draw.circle(surf, (255,255,255), (int(joy_knob[0]), int(joy_knob[1])), JOY_R//2, 2)

# =========================================================
# FIRE button (touch)
# =========================================================
FIRE_BTN = pygame.Rect(BASE_W - 150, BASE_H - 150, 120, 120)
touch_fire = False
fire_touch_id = None

def draw_fire_btn(surf):
    pygame.draw.rect(surf, (200, 60, 60), FIRE_BTN, border_radius=16)
    pygame.draw.rect(surf, (255,255,255), FIRE_BTN, 2, border_radius=16)
    t = ui_font.render("FIRE", True, (255,255,255))
    surf.blit(t, (FIRE_BTN.centerx - t.get_width()//2, FIRE_BTN.centery - t.get_height()//2))

# =========================================================
# LOOK AREA: mitad derecha de la pantalla (sin tapar FIRE)
# =========================================================
LOOK_AREA = pygame.Rect(BASE_W//2, 0, BASE_W//2, BASE_H)

touch_look_active = False
look_touch_id = None
look_lastx = 0

def draw_look_area_hint(surf):
    # dibujamos borde (opcional) pero recortado para que no tape FIRE
    pygame.draw.rect(surf, (255,255,255), LOOK_AREA, 1)
    # "agujero" visual sobre FIRE (solo guía)
    pygame.draw.rect(surf, (0,0,0), FIRE_BTN.inflate(6, 6), 1)

# =========================================================
# Enemigos + Fireballs
# =========================================================
class Enemy:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.hp = 70
        self.cool = random.uniform(0.8, 1.8)

class Fireball:
    def __init__(self, x, y, vx, vy):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.life = 4.0

enemies = []
fireballs = []

def line_of_sight(px, py, tx, ty):
    ang = math.atan2(ty - py, tx - px)
    dist_target = math.hypot(tx - px, ty - py)
    d, _, _ = cast_ray(px, py, ang)
    return d + 0.15 >= dist_target

def spawn_some_enemies(px, py):
    enemies.clear()
    fireballs.clear()
    tries = 0
    while len(enemies) < 6 and tries < 2000:
        tries += 1
        gx = random.randint(1, MAP_W - 2)
        gy = random.randint(1, MAP_H - 2)
        if WORLD_MAP[gy][gx] == "0":
            ex, ey = gx + 0.5, gy + 0.5
            if math.hypot(ex - px, ey - py) > 4.0:
                enemies.append(Enemy(ex, ey))

# sprites placeholders
enemy_sprite = pygame.Surface((64, 64), pygame.SRCALPHA)
pygame.draw.circle(enemy_sprite, (220, 60, 60), (32, 32), 28)
pygame.draw.circle(enemy_sprite, (0, 0, 0), (24, 26), 6)
pygame.draw.circle(enemy_sprite, (0, 0, 0), (40, 26), 6)
pygame.draw.rect(enemy_sprite, (0,0,0), (18, 40, 28, 10), border_radius=5)

fire_sprite = pygame.Surface((32, 32), pygame.SRCALPHA)
pygame.draw.circle(fire_sprite, (255, 120, 0), (16, 16), 12)
pygame.draw.circle(fire_sprite, (255, 220, 0), (16, 16), 7)

def draw_sprite(surf, sprite, sx, sy, size):
    if size <= 2:
        return
    img = pygame.transform.scale(sprite, (size, size))
    surf.blit(img, (sx - size//2, sy - size//2))

# =========================================================
# 1 ARMA: pistola (hitscan)
# =========================================================
WEAPON_NAME = "PISTOL"
SHOT_RATE = 0.35
SHOT_DAMAGE = 22
shot_timer = 0.0
muzzle_timer = 0.0

def best_target_in_crosshair(px, py, pa, zbuf_px):
    center_x = BASE_W // 2
    best = None
    best_dist = 1e9
    for en in enemies:
        if en.hp <= 0:
            continue
        dx = en.x - px
        dy = en.y - py
        dist = math.hypot(dx, dy)
        if dist < 0.35 or dist > MAX_DEPTH:
            continue

        ang = math.atan2(dy, dx)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue

        screen_x = int((diff + HALF_FOV) / FOV * BASE_W)
        if abs(screen_x - center_x) > 28:
            continue

        if 0 <= screen_x < BASE_W:
            if dist > zbuf_px[screen_x] + 0.10:
                continue

        if dist < best_dist and line_of_sight(px, py, en.x, en.y):
            best_dist = dist
            best = en
    return best

def shoot(px, py, pa, zbuf_px):
    global shot_timer, muzzle_timer
    if shot_timer > 0:
        return
    shot_timer = SHOT_RATE
    muzzle_timer = 0.08
    target = best_target_in_crosshair(px, py, pa, zbuf_px)
    if target:
        target.hp -= SHOT_DAMAGE

# =========================================================
# PLAYER
# =========================================================
px, py = find_spawn()
pa = 0.0
player_hp = 100
hurt_cd = 0.0

spawn_some_enemies(px, py)

pygame.event.set_grab(True)
pygame.mouse.set_pos((SCREEN_W//2, SCREEN_H//2))

running = True
while running:
    dt = clock.tick(FPS) / 1000.0

    if shot_timer > 0: shot_timer -= dt
    if muzzle_timer > 0: muzzle_timer -= dt
    if hurt_cd > 0: hurt_cd -= dt

    touch_fire = False

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                running = False

        # Mouse look (PC)
        if e.type == pygame.MOUSEMOTION:
            relx, _ = e.rel
            pa = (pa + relx * MOUSE_SENS) % (2*math.pi)

        if e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                touch_fire = True

        # Touch
        if e.type == pygame.FINGERDOWN:
            sxp = int(e.x * SCREEN_W)
            syp = int(e.y * SCREEN_H)
            x, y, inside = screen_to_base(sxp, syp)
            if not inside:
                continue

            # 1) FIRE siempre primero (prioridad)
            if FIRE_BTN.collidepoint(x, y):
                touch_fire = True
                fire_touch_id = e.finger_id
                continue

            # 2) Movimiento con joystick (mitad izquierda)
            if LEFT_HALF.collidepoint(x, y):
                touch_move_active = True
                move_touch_id = e.finger_id
                JOY_CENTER[0], JOY_CENTER[1] = x, y
                set_joy_from_pos(x, y)
                continue

            # 3) Look: mitad derecha (pero NO dentro del FIRE)
            if LOOK_AREA.collidepoint(x, y) and (not FIRE_BTN.collidepoint(x, y)):
                touch_look_active = True
                look_touch_id = e.finger_id
                look_lastx = x
                continue

        if e.type == pygame.FINGERMOTION:
            sxp = int(e.x * SCREEN_W)
            syp = int(e.y * SCREEN_H)
            x, y, inside = screen_to_base(sxp, syp)
            if not inside:
                continue

            if touch_look_active and e.finger_id == look_touch_id:
                dx = x - look_lastx
                look_lastx = x
                pa = (pa + dx * 0.010) % (2*math.pi)

            if touch_move_active and e.finger_id == move_touch_id:
                set_joy_from_pos(x, y)

        if e.type == pygame.FINGERUP:
            if e.finger_id == fire_touch_id:
                fire_touch_id = None
            if touch_look_active and e.finger_id == look_touch_id:
                touch_look_active = False
                look_touch_id = None
            if touch_move_active and e.finger_id == move_touch_id:
                touch_move_active = False
                move_touch_id = None
                reset_joystick()

    # =========================================================
    # Movimiento: WASD + Joystick (WASD)
    # =========================================================
    keys = pygame.key.get_pressed()
    forward = (1 if keys[pygame.K_w] else 0) + (-1 if keys[pygame.K_s] else 0)
    strafe  = (1 if keys[pygame.K_d] else 0) + (-1 if keys[pygame.K_a] else 0)

    # Touch joystick suma
    forward += joy_move_y
    strafe  += joy_move_x

    forward = clamp(forward, -1.0, 1.0)
    strafe  = clamp(strafe, -1.0, 1.0)

    dx = math.cos(pa)
    dy = math.sin(pa)
    sxv = -dy
    syv = dx

    nx = px + (dx * forward + sxv * strafe) * MOVE_SPEED * dt
    ny = py + (dy * forward + syv * strafe) * MOVE_SPEED * dt

    if not is_wall(nx, py): px = nx
    if not is_wall(px, ny): py = ny

    # =========================================================
    # Render 3D + zbuffer por pixel
    # =========================================================
    base.fill((0, 0, 0))
    pygame.draw.rect(base, (35, 35, 55), (0, 0, BASE_W, BASE_H // 2))
    pygame.draw.rect(base, (25, 22, 18), (0, BASE_H // 2, BASE_W, BASE_H // 2))

    start_angle = pa - HALF_FOV
    ray_step = FOV / NUM_RAYS
    col_w = BASE_W / NUM_RAYS

    zbuf_px = [MAX_DEPTH] * BASE_W

    for i in range(NUM_RAYS):
        angle = start_angle + i * ray_step
        dist, shade, tex_u = cast_ray(px, py, angle)
        dist_corr = dist * math.cos(pa - angle)
        dist_corr = max(0.01, dist_corr)

        wall_h = int((BASE_H * 0.9) / dist_corr)
        wall_h = min(BASE_H, wall_h)
        y0 = (BASE_H // 2) - (wall_h // 2)

        tex_x = int(tex_u * (TEX_SIZE - 1))
        tex_x = int(clamp(tex_x, 0, TEX_SIZE - 1))

        w = int(col_w) + 1
        x0 = int(i * col_w)

        col = TEX_COLS[tex_x]
        col_scaled = pygame.transform.scale(col, (w, wall_h))

        fog = clamp(1.0 - (dist_corr / MAX_DEPTH), 0.15, 1.0)
        intensity = fog * shade
        mult = int(255 * intensity)

        img = col_scaled.copy()
        img.fill((mult, mult, mult), special_flags=pygame.BLEND_RGB_MULT)
        base.blit(img, (x0, y0))

        for xx in range(x0, min(BASE_W, x0 + w)):
            zbuf_px[xx] = dist_corr

    # =========================================================
    # Enemigos disparan + fuego
    # =========================================================
    for en in enemies[:]:
        if en.hp <= 0:
            enemies.remove(en)
            continue

        dist = math.hypot(en.x - px, en.y - py)
        en.cool -= dt

        if dist < 12.0 and en.cool <= 0.0 and line_of_sight(px, py, en.x, en.y):
            en.cool = random.uniform(0.8, 1.6)
            ang = math.atan2(py - en.y, px - en.x)
            spd = 5.0
            fireballs.append(Fireball(en.x, en.y, math.cos(ang)*spd, math.sin(ang)*spd))

    for fb in fireballs[:]:
        fb.life -= dt
        if fb.life <= 0:
            fireballs.remove(fb)
            continue

        nx = fb.x + fb.vx * dt
        ny = fb.y + fb.vy * dt
        if is_wall(nx, ny):
            fireballs.remove(fb)
            continue
        fb.x, fb.y = nx, ny

        if math.hypot(fb.x - px, fb.y - py) < 0.35 and hurt_cd <= 0:
            player_hp -= 12
            hurt_cd = 0.6
            fireballs.remove(fb)
            if player_hp <= 0:
                px, py = find_spawn()
                pa = 0.0
                player_hp = 100
                spawn_some_enemies(px, py)

    # =========================================================
    # Render sprites (enemigos + fireballs)
    # =========================================================
    for en in enemies:
        dxp = en.x - px
        dyp = en.y - py
        dist = math.hypot(dxp, dyp)
        if dist < 0.01 or dist > MAX_DEPTH:
            continue
        ang = math.atan2(dyp, dxp)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue

        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        size = int((BASE_H * 0.85) / dist)
        size = int(clamp(size, 8, 260))

        if 0 <= sx < BASE_W and dist <= zbuf_px[sx] + 0.10:
            draw_sprite(base, enemy_sprite, sx, BASE_H//2 + size//6, size)

    for fb in fireballs:
        dxp = fb.x - px
        dyp = fb.y - py
        dist = math.hypot(dxp, dyp)
        if dist < 0.01 or dist > MAX_DEPTH:
            continue
        ang = math.atan2(dyp, dxp)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue

        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        size = int((BASE_H * 0.35) / dist)
        size = int(clamp(size, 6, 90))

        if 0 <= sx < BASE_W and dist <= zbuf_px[sx] + 0.08:
            draw_sprite(base, fire_sprite, sx, BASE_H//2, size)

    # =========================================================
    # Disparo (cuando ya existe zbuffer)
    # =========================================================
    if touch_fire:
        shoot(px, py, pa, zbuf_px)

    # =========================================================
    # UI
    # =========================================================
    draw_joystick(base)
    draw_fire_btn(base)
    draw_crosshair(base)
    draw_look_area_hint(base)

    hp_txt = ui_font.render(f"HP: {player_hp}", True, (255,255,255))
    we_txt = ui_font.render(f"WEAPON: {WEAPON_NAME}", True, (255,255,255))
    en_txt = ui_font.render(f"ENEMIES: {len(enemies)}", True, (255,255,255))
    base.blit(hp_txt, (10, 10))
    base.blit(we_txt, (10, 32))
    base.blit(en_txt, (10, 54))

    if muzzle_timer > 0:
        pygame.draw.circle(base, (255, 230, 120), (BASE_W//2, BASE_H//2), 18)

    # =========================================================
    # Presentación con letterbox
    # =========================================================
    scaled = pygame.transform.scale(base, (FINAL_W, FINAL_H))
    screen.fill((0, 0, 0))
    screen.blit(scaled, (OFF_X, OFF_Y))
    pygame.display.flip()

pygame.quit()
sys.exit()
