import math
import sys
import os
import pygame
import random

pygame.init()
pygame.mixer.init()

# =========================================================
# Pantalla real (fullscreen) + render interno (más rápido)
# =========================================================
pygame.display.set_caption("Raycaster DOOM-lite (Melee + Fireballs + Drops)")
pygame.mouse.set_visible(False)

# Render interno (mejor FPS)
BASE_W, BASE_H = 960, 540   # si va lento: 800,450
base = pygame.Surface((BASE_W, BASE_H))

# ---------- FULLSCREEN toggle con F11 ----------
FULLSCREEN = True

def create_screen(fullscreen: bool):
    flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
    if fullscreen:
        scr = pygame.display.set_mode((0, 0), flags)
        inf = pygame.display.Info()
        return scr, inf.current_w, inf.current_h
    else:
        scr = pygame.display.set_mode((1280, 720), flags)
        inf = pygame.display.Info()
        return scr, inf.current_w, inf.current_h

screen, SCREEN_W, SCREEN_H = create_screen(FULLSCREEN)

def recompute_scale():
    global scale, FINAL_W, FINAL_H, OFF_X, OFF_Y
    scale = min(SCREEN_W / BASE_W, SCREEN_H / BASE_H)
    FINAL_W, FINAL_H = int(BASE_W * scale), int(BASE_H * scale)
    OFF_X = (SCREEN_W - FINAL_W) // 2
    OFF_Y = (SCREEN_H - FINAL_H) // 2

recompute_scale()
# ----------------------------------------------

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

# IA
ENEMY_SPEED = 1.55
ENEMY_STOP_DIST = 1.05

# RANGED
ENEMY_FIRE_RANGE = 10.5
ENEMY_FIRE_COOLDOWN = (0.8, 1.45)

# MELEE
ENEMY_MELEE_RANGE = 1.25
ENEMY_MELEE_COOLDOWN = (0.55, 0.85)
MELEE_DAMAGE = 16

# Combate
PLAYER_MAX_HP = 100
FIREBALL_DAMAGE = 12

# Weapon / Ammo
AMMO_MAX = 200
AMMO_START = 40
AMMO_PER_SHOT = 1
SHOT_RATE = 0.18
SHOT_DAMAGE = 24

# Drops + pickups
DROP_CHANCE = 0.75
DROP_HEALTH_CHANCE = 0.45
DROP_AMMO_CHANCE = 0.75

HEALTH_PACK_AMOUNT = 25
AMMO_PICKUP_AMOUNT = 18
PICKUP_RADIUS = 0.55

# =========================================================
# Utils
# =========================================================
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

def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)

# =========================================================
# Detectar Android (Pydroid) -> HUD touch
# =========================================================
IS_ANDROID = (sys.platform == "android") or ("ANDROID_ARGUMENT" in os.environ)
show_touch_hud = IS_ANDROID

# =========================================================
# ASSETS DIR (TU RUTA)
# =========================================================
def pick_assets_dir():
    candidates = []
    if "__file__" in globals():
        candidates.append(os.path.join(os.path.dirname(__file__), "assets"))
    candidates.append("assets")
    candidates.append("/storage/emulated/0/Download/laberint/assets")
    candidates.append("/storage/emulated/0/Downloads/laberint/assets")
    for p in candidates:
        if p and os.path.isdir(p):
            return p
    return "assets"

ASSETS_DIR = pick_assets_dir()

# =========================================================
# SONIDOS (si falta algo, no crashea)
# =========================================================
class _NullSound:
    def play(self): pass
    def set_volume(self, v): pass

def load_sound_file(filename):
    p = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(p):
        try:
            return pygame.mixer.Sound(p)
        except:
            return _NullSound()
    return _NullSound()

# Cambiá nombres si tus archivos tienen otro nombre
SND_SHOT = load_sound_file("shot.ogg")
SND_FIREBALL_HIT = load_sound_file("fireball_hit.ogg")
SND_DEMON_SHOT = load_sound_file("demon_shoot.ogg")
SND_DEMON_DIE  = load_sound_file("demon_die.ogg")
SND_PICKUP     = load_sound_file("pickup.ogg")
SND_HURT       = load_sound_file("hurt.ogg")
SND_EMPTY      = load_sound_file("empty.ogg")
SND_MELEE      = load_sound_file("melee.ogg")

for s, v in [
    (SND_SHOT, 0.78),
    (SND_FIREBALL_HIT, 0.75),
    (SND_DEMON_SHOT, 0.70),
    (SND_DEMON_DIE, 0.78),
    (SND_PICKUP, 0.85),
    (SND_HURT, 0.85),
    (SND_EMPTY, 0.70),
    (SND_MELEE, 0.85),
]:
    try:
        s.set_volume(v)
    except:
        pass

# =========================================================
# Imagen arma
# =========================================================
def load_image_file(filename):
    p = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(p):
        try:
            return pygame.image.load(p).convert_alpha()
        except:
            return None
    return None

PISTOL_IMG = load_image_file("pistol.png")

# =========================================================
# MAP
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

# =========================================================
# Textura pared
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
        distv = (map_x - px + (1 - step_x) / 2) / (ray_dx + EPS)
        hit = py + distv * ray_dy
        tex_u = hit - math.floor(hit)
        if ray_dx > 0:
            tex_u = 1.0 - tex_u
        shade = 0.75
    else:
        distv = (map_y - py + (1 - step_y) / 2) / (ray_dy + EPS)
        hit = px + distv * ray_dx
        tex_u = hit - math.floor(hit)
        if ray_dy < 0:
            tex_u = 1.0 - tex_u
        shade = 1.0

    distv = max(0.01, min(MAX_DEPTH, distv))
    return distv, shade, tex_u

def line_of_sight(px, py, tx, ty):
    ang = math.atan2(ty - py, tx - px)
    dist_target = math.hypot(tx - px, ty - py)
    d, _, _ = cast_ray(px, py, ang)
    return d + 0.15 >= dist_target

# =========================================================
# INPUT mapping: pantalla real -> base
# =========================================================
def screen_to_base(sx, sy):
    bx = (sx - OFF_X) / scale
    by = (sy - OFF_Y) / scale
    inside = (0 <= bx < BASE_W) and (0 <= by < BASE_H)
    return int(bx), int(by), inside

# =========================================================
# UI + HUD touch
# =========================================================
ui_font = pygame.font.SysFont(None, 22)

def draw_crosshair(surf):
    cx, cy = BASE_W // 2, BASE_H // 2
    pygame.draw.line(surf, (255, 255, 255), (cx - 8, cy), (cx + 8, cy), 1)
    pygame.draw.line(surf, (255, 255, 255), (cx, cy - 8), (cx, cy + 8), 1)

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
    joy_move_x = dz(vx / JOY_R)
    joy_move_y = -dz(vy / JOY_R)

def reset_joystick():
    global joy_move_x, joy_move_y
    joy_knob[0], joy_knob[1] = JOY_CENTER[0], JOY_CENTER[1]
    joy_move_x, joy_move_y = 0.0, 0.0

def draw_joystick(surf):
    pygame.draw.circle(surf, (255, 255, 255), (int(JOY_CENTER[0]), int(JOY_CENTER[1])), JOY_R, 2)
    pygame.draw.circle(surf, (255, 255, 255), (int(joy_knob[0]), int(joy_knob[1])), JOY_R // 2, 2)

FIRE_BTN = pygame.Rect(BASE_W - 150, BASE_H - 150, 120, 120)
touch_fire = False

def draw_fire_btn(surf):
    pygame.draw.rect(surf, (200, 60, 60), FIRE_BTN, border_radius=16)
    pygame.draw.rect(surf, (255, 255, 255), FIRE_BTN, 2, border_radius=16)
    t = ui_font.render("FIRE", True, (255, 255, 255))
    surf.blit(t, (FIRE_BTN.centerx - t.get_width() // 2, FIRE_BTN.centery - t.get_height() // 2))

# =========================================================
# ENTIDADES
# =========================================================
class Enemy:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.max_hp = 90
        self.hp = self.max_hp
        self.fire_cd = random.uniform(*ENEMY_FIRE_COOLDOWN)
        self.melee_cd = random.uniform(*ENEMY_MELEE_COOLDOWN)
        self.wander = random.uniform(0.0, 9999.0)
        self.state = "walk"   # walk / attack / die / melee
        self.anim_t = 0.0
        self.die_t = 0.0

class Fireball:
    def __init__(self, x, y, vx, vy):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.life = 4.0

class Pickup:
    def __init__(self, x, y, kind="health"):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.bob = random.uniform(0.0, 10.0)

enemies = []
fireballs = []
pickups = []

def random_empty_cell_far(px, py, min_dist=3.0):
    for _ in range(4000):
        gx = random.randint(1, MAP_W - 2)
        gy = random.randint(1, MAP_H - 2)
        if WORLD_MAP[gy][gx] == "0":
            x, y = gx + 0.5, gy + 0.5
            if dist(x, y, px, py) >= min_dist:
                return x, y
    return None

def spawn_some_enemies(px, py, count=8):
    enemies.clear()
    fireballs.clear()
    tries = 0
    while len(enemies) < count and tries < 7000:
        tries += 1
        pos = random_empty_cell_far(px, py, min_dist=4.0)
        if not pos:
            break
        ex, ey = pos
        enemies.append(Enemy(ex, ey))

def spawn_map_pickups(px, py, medkits=10, ammo=14):
    pickups.clear()
    used = set()
    def place(kind, n):
        tries = 0
        while n > 0 and tries < 9000:
            tries += 1
            pos = random_empty_cell_far(px, py, min_dist=2.5)
            if not pos:
                break
            x, y = pos
            key = (int(x*2), int(y*2), kind)
            if key in used:
                continue
            used.add(key)
            pickups.append(Pickup(x, y, kind))
            n -= 1
    place("health", medkits)
    place("ammo", ammo)

def move_entity_with_collision(x, y, vx, vy):
    nx = x + vx
    ny = y + vy
    if not is_wall(nx, y):
        x = nx
    if not is_wall(x, ny):
        y = ny
    return x, y

# =========================================================
# Sprites demon (anim) + fireball + pickups
# (SIN BRAZOS)
# =========================================================
def demon_sprite_walk(frame):
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    bob = [0, 2, 0, -2][frame % 4]

    # cuerpo
    pygame.draw.ellipse(s, (145, 20, 20), (16, 18 + bob, 64, 62))
    pygame.draw.ellipse(s, (60, 0, 0), (20, 22 + bob, 56, 54), 3)

    # cuernos
    horn_col = (200, 200, 200)
    pygame.draw.polygon(s, horn_col, [(26, 26 + bob), (10, 14 + bob), (26, 40 + bob)])
    pygame.draw.polygon(s, horn_col, [(70, 26 + bob), (86, 14 + bob), (70, 40 + bob)])

    # ojos
    eye_y = 36 + bob
    pygame.draw.ellipse(s, (255, 220, 0), (34, eye_y, 10, 8))
    pygame.draw.ellipse(s, (255, 220, 0), (52, eye_y, 10, 8))
    pygame.draw.circle(s, (0, 0, 0), (39, eye_y + 4), 2)
    pygame.draw.circle(s, (0, 0, 0), (57, eye_y + 4), 2)

    # boca
    mouth_y = 54 + bob
    pygame.draw.ellipse(s, (20, 0, 0), (38, mouth_y, 24, 14))
    pygame.draw.polygon(s, (240, 240, 240), [(44, mouth_y + 6), (48, mouth_y + 6), (46, mouth_y + 12)])
    pygame.draw.polygon(s, (240, 240, 240), [(52, mouth_y + 6), (56, mouth_y + 6), (54, mouth_y + 12)])
    return s

def demon_sprite_attack(frame):
    # dispara "magia" desde la boca (sin brazos)
    s = pygame.Surface((96, 96), pygame.SRCALPHA)

    pygame.draw.ellipse(s, (150, 25, 25), (16, 18, 64, 62))
    pygame.draw.ellipse(s, (60, 0, 0), (20, 22, 56, 54), 3)

    horn_col = (200, 200, 200)
    pygame.draw.polygon(s, horn_col, [(26, 26), (10, 12), (26, 40)])
    pygame.draw.polygon(s, horn_col, [(70, 26), (86, 12), (70, 40)])

    pygame.draw.ellipse(s, (255, 220, 0), (34, 36, 10, 8))
    pygame.draw.ellipse(s, (255, 220, 0), (52, 36, 10, 8))

    # boca grande + brillo de fuego
    pygame.draw.ellipse(s, (20, 0, 0), (32, 52, 32, 22))
    pygame.draw.circle(s, (255, 120, 0), (48, 64), 11)
    pygame.draw.circle(s, (255, 220, 0), (48, 64), 7)
    pygame.draw.circle(s, (255, 255, 255), (48, 64), 3)

    for tx in (40, 48, 56):
        pygame.draw.polygon(s, (240, 240, 240), [(tx-2, 58), (tx+2, 58), (tx, 66)])

    return s

def demon_sprite_melee(frame):
    # mordida: sin brazos
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    lunge = [0, 4, 8, 4][frame % 4]
    pygame.draw.ellipse(s, (155, 25, 25), (16, 18 - lunge, 64, 62))
    pygame.draw.ellipse(s, (60, 0, 0), (20, 22 - lunge, 56, 54), 3)
    horn_col = (200, 200, 200)
    pygame.draw.polygon(s, horn_col, [(26, 26 - lunge), (10, 12 - lunge), (26, 40 - lunge)])
    pygame.draw.polygon(s, horn_col, [(70, 26 - lunge), (86, 12 - lunge), (70, 40 - lunge)])
    pygame.draw.ellipse(s, (255, 220, 0), (34, 36 - lunge, 10, 8))
    pygame.draw.ellipse(s, (255, 220, 0), (52, 36 - lunge, 10, 8))
    pygame.draw.ellipse(s, (20, 0, 0), (30, 50 - lunge, 36, 26))
    for tx in (38, 46, 54, 62):
        pygame.draw.polygon(s, (240, 240, 240), [(tx, 56 - lunge), (tx+4, 56 - lunge), (tx+2, 66 - lunge)])
    return s

def demon_sprite_die(frame):
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    shrink = frame * 4
    alpha = int(clamp(255 - frame * 40, 0, 255))
    body = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(body, (145, 20, 20), (16, 18, 64, 62))
    pygame.draw.ellipse(body, (60, 0, 0), (20, 22, 56, 54), 3)
    pygame.draw.ellipse(body, (120, 120, 0), (34, 36, 10, 8))
    pygame.draw.ellipse(body, (120, 120, 0), (52, 36, 10, 8))
    body.set_alpha(alpha)
    w = max(10, 96 - shrink)
    h = max(10, 96 - shrink)
    scaled = pygame.transform.smoothscale(body, (w, h))
    s.blit(scaled, ((96 - w)//2, (96 - h)//2 + frame*3))
    return s

DEMON_WALK_FRAMES = [demon_sprite_walk(i) for i in range(4)]
DEMON_ATTACK_FRAMES = [demon_sprite_attack(i) for i in range(4)]
DEMON_MELEE_FRAMES = [demon_sprite_melee(i) for i in range(4)]
DEMON_DIE_FRAMES = [demon_sprite_die(i) for i in range(6)]

fire_sprite = pygame.Surface((32, 32), pygame.SRCALPHA)
pygame.draw.circle(fire_sprite, (255, 120, 0), (16, 16), 12)
pygame.draw.circle(fire_sprite, (255, 220, 0), (16, 16), 7)

health_sprite = pygame.Surface((40, 40), pygame.SRCALPHA)
pygame.draw.rect(health_sprite, (220, 220, 220), (6, 6, 28, 28), border_radius=6)
pygame.draw.rect(health_sprite, (220, 40, 40), (17, 10, 6, 20))
pygame.draw.rect(health_sprite, (220, 40, 40), (10, 17, 20, 6))

ammo_sprite = pygame.Surface((40, 40), pygame.SRCALPHA)
pygame.draw.rect(ammo_sprite, (210, 190, 80), (6, 8, 28, 24), border_radius=6)
pygame.draw.rect(ammo_sprite, (80, 60, 20), (6, 8, 28, 24), 2, border_radius=6)
pygame.draw.rect(ammo_sprite, (240, 240, 240), (12, 14, 16, 12), border_radius=3)

def draw_sprite(surf, sprite, sx, sy, size, alpha=255):
    if size <= 2:
        return
    img = pygame.transform.scale(sprite, (size, size))
    if alpha != 255:
        img = img.copy()
        img.set_alpha(alpha)
    surf.blit(img, (sx - size // 2, sy - size // 2))

# =========================================================
# ARMA + disparo
# =========================================================
shot_timer = 0.0
muzzle_timer = 0.0
recoil = 0.0

def best_target_in_crosshair(px, py, pa, zbuf_px):
    center_x = BASE_W // 2
    best = None
    best_dist = 1e9
    for en in enemies:
        if en.hp <= 0:
            continue
        dx = en.x - px
        dy = en.y - py
        d = math.hypot(dx, dy)
        if d < 0.35 or d > MAX_DEPTH:
            continue
        ang = math.atan2(dy, dx)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue
        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        if abs(sx - center_x) > 28:
            continue
        if 0 <= sx < BASE_W:
            if d > zbuf_px[sx] + 0.10:
                continue
        if d < best_dist and line_of_sight(px, py, en.x, en.y):
            best_dist = d
            best = en
    return best

def shoot(px, py, pa, zbuf_px, ammo_ref):
    global shot_timer, muzzle_timer, recoil
    if shot_timer > 0:
        return
    if ammo_ref[0] < AMMO_PER_SHOT:
        SND_EMPTY.play()
        shot_timer = 0.12
        return

    ammo_ref[0] -= AMMO_PER_SHOT
    shot_timer = SHOT_RATE
    muzzle_timer = 0.08
    recoil = 1.0
    SND_SHOT.play()

    target = best_target_in_crosshair(px, py, pa, zbuf_px)
    if target and target.state != "die":
        target.hp -= SHOT_DAMAGE
        if target.hp <= 0 and target.state != "die":
            target.state = "die"
            target.die_t = 0.0
            SND_DEMON_DIE.play()
            if random.random() < DROP_CHANCE:
                if random.random() < DROP_AMMO_CHANCE:
                    pickups.append(Pickup(target.x, target.y, "ammo"))
                if random.random() < DROP_HEALTH_CHANCE:
                    pickups.append(Pickup(target.x + random.uniform(-0.15, 0.15),
                                          target.y + random.uniform(-0.15, 0.15), "health"))

def draw_weapon_fp(surf, move_mag, t, recoil_amt, muzzle):
    bob = math.sin(t * 10.0) * 6.0 * clamp(move_mag, 0.0, 1.0)
    bob2 = math.cos(t * 7.0) * 3.0 * clamp(move_mag, 0.0, 1.0)
    kick = recoil_amt * 14.0
    cx = BASE_W // 2
    y = BASE_H - 10

    if PISTOL_IMG:
        target_w = int(BASE_W * 0.34)
        ratio = target_w / PISTOL_IMG.get_width()
        target_h = int(PISTOL_IMG.get_height() * ratio)
        img = pygame.transform.smoothscale(PISTOL_IMG, (target_w, target_h))
        gx = cx - target_w // 2 + int(bob2)
        gy = y - target_h + int(bob) - int(kick)
        surf.blit(img, (gx, gy))
        if muzzle > 0:
            fx = gx + int(target_w * 0.82)
            fy = gy + int(target_h * 0.38)
            pygame.draw.circle(surf, (255, 230, 120), (fx, fy), 18)
            pygame.draw.circle(surf, (255, 180, 60), (fx, fy), 10)
            pygame.draw.circle(surf, (255, 255, 255), (fx, fy), 5)

# =========================================================
# PLAYER INIT
# =========================================================
px, py = find_spawn()
pa = 0.0
player_hp = PLAYER_MAX_HP
ammo = [AMMO_START]
hurt_cd = 0.0

spawn_some_enemies(px, py, count=8)
spawn_map_pickups(px, py, medkits=10, ammo=14)

# Mouse lock solo en PC
if not IS_ANDROID:
    pygame.event.set_grab(True)

running = True
time_acc = 0.0

while running:
    dt = clock.tick(FPS) / 1000.0
    time_acc += dt

    if shot_timer > 0: shot_timer -= dt
    if muzzle_timer > 0: muzzle_timer -= dt
    if hurt_cd > 0: hurt_cd -= dt
    recoil = max(0.0, recoil - dt * 6.0)

    touch_fire = False

    # =======================
    # Eventos + Auto HUD + F11
    # =======================
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.KEYDOWN:
            # teclado = ocultar HUD
            show_touch_hud = False

            if e.key == pygame.K_ESCAPE:
                running = False

            if e.key == pygame.K_F11:
                FULLSCREEN = not FULLSCREEN
                screen, SCREEN_W, SCREEN_H = create_screen(FULLSCREEN)
                recompute_scale()
                if not IS_ANDROID:
                    pygame.event.set_grab(True)

        if e.type == pygame.VIDEORESIZE:
            # ventana redimensionable
            if not FULLSCREEN:
                SCREEN_W, SCREEN_H = e.w, e.h
                recompute_scale()

        if e.type == pygame.MOUSEMOTION:
            # mouse = ocultar HUD
            show_touch_hud = False
            relx, _ = e.rel
            pa = (pa + relx * MOUSE_SENS) % (2 * math.pi)

        if e.type == pygame.MOUSEBUTTONDOWN:
            show_touch_hud = False
            if e.button == 1:
                touch_fire = True

        if e.type == pygame.FINGERDOWN:
            # touch = mostrar HUD
            show_touch_hud = True
            sxp = int(e.x * SCREEN_W)
            syp = int(e.y * SCREEN_H)
            x, y, inside = screen_to_base(sxp, syp)
            if not inside:
                continue

            if FIRE_BTN.collidepoint(x, y):
                touch_fire = True
                continue

            if LEFT_HALF.collidepoint(x, y):
                touch_move_active = True
                move_touch_id = e.finger_id
                JOY_CENTER[0], JOY_CENTER[1] = x, y
                set_joy_from_pos(x, y)
                continue

        if e.type == pygame.FINGERMOTION:
            show_touch_hud = True
            sxp = int(e.x * SCREEN_W)
            syp = int(e.y * SCREEN_H)
            x, y, inside = screen_to_base(sxp, syp)
            if not inside:
                continue
            if touch_move_active and e.finger_id == move_touch_id:
                set_joy_from_pos(x, y)

        if e.type == pygame.FINGERUP:
            if touch_move_active and e.finger_id == move_touch_id:
                touch_move_active = False
                move_touch_id = None
                reset_joystick()

    # =======================
    # Movimiento: WASD + joystick
    # =======================
    keys = pygame.key.get_pressed()
    forward = (1 if keys[pygame.K_w] else 0) + (-1 if keys[pygame.K_s] else 0)
    strafe  = (1 if keys[pygame.K_d] else 0) + (-1 if keys[pygame.K_a] else 0)

    if show_touch_hud:
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

    move_mag = clamp(math.hypot(forward, strafe), 0.0, 1.0)

    # =======================
    # Pickups
    # =======================
    for it in pickups[:]:
        if dist(px, py, it.x, it.y) < PICKUP_RADIUS:
            if it.kind == "health" and player_hp < PLAYER_MAX_HP:
                player_hp = min(PLAYER_MAX_HP, player_hp + HEALTH_PACK_AMOUNT)
                SND_PICKUP.play()
                pickups.remove(it)
            elif it.kind == "ammo" and ammo[0] < AMMO_MAX:
                ammo[0] = min(AMMO_MAX, ammo[0] + AMMO_PICKUP_AMOUNT)
                SND_PICKUP.play()
                pickups.remove(it)

    # =======================
    # Render 3D + zbuffer
    # =======================
    base.fill((0, 0, 0))
    pygame.draw.rect(base, (35, 35, 55), (0, 0, BASE_W, BASE_H // 2))
    pygame.draw.rect(base, (25, 22, 18), (0, BASE_H // 2, BASE_W, BASE_H // 2))

    start_angle = pa - HALF_FOV
    ray_step = FOV / NUM_RAYS
    col_w = BASE_W / NUM_RAYS
    zbuf_px = [MAX_DEPTH] * BASE_W

    for i in range(NUM_RAYS):
        angle = start_angle + i * ray_step
        distv, shade, tex_u = cast_ray(px, py, angle)
        dist_corr = distv * math.cos(pa - angle)
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

    # =======================
    # IA Demonios: melee + bolas de fuego
    # =======================
    for en in enemies[:]:
        en.anim_t += dt

        if en.state == "die":
            en.die_t += dt
            if en.die_t >= 0.9:
                enemies.remove(en)
            continue

        if en.hp <= 0:
            en.state = "die"
            en.die_t = 0.0
            continue

        en.fire_cd -= dt
        en.melee_cd -= dt
        d_to_player = dist(en.x, en.y, px, py)

        if d_to_player > ENEMY_STOP_DIST:
            ax = (px - en.x) / (d_to_player + 1e-6)
            ay = (py - en.y) / (d_to_player + 1e-6)
            wob = math.sin(time_acc * 2.1 + en.wander) * 0.25
            wx = -ay * wob
            wy = ax * wob
            spd = ENEMY_SPEED * dt
            vx = (ax + wx) * spd
            vy = (ay + wy) * spd
            en.x, en.y = move_entity_with_collision(en.x, en.y, vx, vy)

        # MELEE
        if d_to_player <= ENEMY_MELEE_RANGE and en.melee_cd <= 0.0 and line_of_sight(en.x, en.y, px, py):
            en.state = "melee"
            en.anim_t = 0.0
            en.melee_cd = random.uniform(*ENEMY_MELEE_COOLDOWN)

            if hurt_cd <= 0.0:
                player_hp -= MELEE_DAMAGE
                hurt_cd = 0.45
                SND_MELEE.play()
                SND_HURT.play()

                if player_hp <= 0:
                    px, py = find_spawn()
                    pa = 0.0
                    player_hp = PLAYER_MAX_HP
                    ammo[0] = AMMO_START
                    spawn_some_enemies(px, py, count=8)
                    spawn_map_pickups(px, py, medkits=10, ammo=14)
            continue

        # RANGED
        if d_to_player < ENEMY_FIRE_RANGE and en.fire_cd <= 0.0 and line_of_sight(en.x, en.y, px, py):
            en.state = "attack"
            en.anim_t = 0.0
            en.fire_cd = random.uniform(*ENEMY_FIRE_COOLDOWN)

            ang = math.atan2(py - en.y, px - en.x)
            spd = 5.2
            fireballs.append(Fireball(en.x, en.y, math.cos(ang) * spd, math.sin(ang) * spd))
            SND_DEMON_SHOT.play()
            continue

        en.state = "walk"

    # =======================
    # Fireballs
    # =======================
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

        if dist(fb.x, fb.y, px, py) < 0.35 and hurt_cd <= 0:
            player_hp -= FIREBALL_DAMAGE
            hurt_cd = 0.6
            fireballs.remove(fb)
            SND_HURT.play()
            SND_FIREBALL_HIT.play()

            if player_hp <= 0:
                px, py = find_spawn()
                pa = 0.0
                player_hp = PLAYER_MAX_HP
                ammo[0] = AMMO_START
                spawn_some_enemies(px, py, count=8)
                spawn_map_pickups(px, py, medkits=10, ammo=14)

    # =======================
    # Disparo
    # =======================
    if touch_fire:
        shoot(px, py, pa, zbuf_px, ammo)

    # =======================
    # Sprites 3D (pickups + demons + fireballs)
    # =======================
    # Pickups
    for it in pickups:
        dxp = it.x - px
        dyp = it.y - py
        distp = math.hypot(dxp, dyp)
        if distp < 0.01 or distp > MAX_DEPTH:
            continue
        ang = math.atan2(dyp, dxp)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue
        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        bob = math.sin(time_acc * 3.2 + it.bob) * 6.0
        size = int((BASE_H * 0.36) / distp)
        size = int(clamp(size, 10, 120))
        if 0 <= sx < BASE_W and distp <= zbuf_px[sx] + 0.08:
            sprite = health_sprite if it.kind == "health" else ammo_sprite
            draw_sprite(base, sprite, sx, int(BASE_H // 2 + size // 3 + bob), size)

    # Demons
    for en in enemies:
        dxp = en.x - px
        dyp = en.y - py
        distp = math.hypot(dxp, dyp)
        if distp < 0.01 or distp > MAX_DEPTH:
            continue
        ang = math.atan2(dyp, dxp)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue
        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        size = int((BASE_H * 1.00) / distp)
        size = int(clamp(size, 14, 360))
        if 0 <= sx < BASE_W and distp <= zbuf_px[sx] + 0.10:
            if en.state == "walk":
                fi = int(en.anim_t * 10) % 4
                draw_sprite(base, DEMON_WALK_FRAMES[fi], sx, BASE_H // 2 + size // 6, size)
            elif en.state == "attack":
                fi = int(en.anim_t * 12) % 4
                draw_sprite(base, DEMON_ATTACK_FRAMES[fi], sx, BASE_H // 2 + size // 6, size)
            elif en.state == "melee":
                fi = int(en.anim_t * 12) % 4
                draw_sprite(base, DEMON_MELEE_FRAMES[fi], sx, BASE_H // 2 + size // 6, size)
            elif en.state == "die":
                fi = int(en.die_t * 7)
                fi = int(clamp(fi, 0, 5))
                draw_sprite(base, DEMON_DIE_FRAMES[fi], sx, BASE_H // 2 + size // 6, size, alpha=255)

    # Fireballs
    for fb in fireballs:
        dxp = fb.x - px
        dyp = fb.y - py
        distp = math.hypot(dxp, dyp)
        if distp < 0.01 or distp > MAX_DEPTH:
            continue
        ang = math.atan2(dyp, dxp)
        diff = ang_wrap(ang - pa)
        if abs(diff) > HALF_FOV:
            continue
        sx = int((diff + HALF_FOV) / FOV * BASE_W)
        size = int((BASE_H * 0.35) / distp)
        size = int(clamp(size, 8, 90))
        if 0 <= sx < BASE_W and distp <= zbuf_px[sx] + 0.08:
            draw_sprite(base, fire_sprite, sx, BASE_H // 2, size)

    # =======================
    # UI + arma
    # =======================
    draw_crosshair(base)

    hp_txt = ui_font.render(f"HP: {player_hp}", True, (255, 255, 255))
    am_txt = ui_font.render(f"AMMO: {ammo[0]}", True, (255, 255, 255))
    dm_txt = ui_font.render(f"DEMONS: {len(enemies)}", True, (255, 255, 255))

    base.blit(hp_txt, (10, 10))
    base.blit(am_txt, (10, 30))
    base.blit(dm_txt, (10, 50))

    if show_touch_hud:
        draw_joystick(base)
        draw_fire_btn(base)

    draw_weapon_fp(base, move_mag, time_acc, recoil, muzzle_timer)

    # =======================
    # Presentación con letterbox
    # =======================
    scaled = pygame.transform.scale(base, (FINAL_W, FINAL_H))
    screen.fill((0, 0, 0))
    screen.blit(scaled, (OFF_X, OFF_Y))
    pygame.display.flip()

pygame.quit()
sys.exit()
