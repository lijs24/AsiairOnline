def build_part(C):
    import numpy as np, math
    parts = []

    # ----- palette -----
    BODY  = (0.12, 0.13, 0.14)   # dark graphite housing
    BODY2 = (0.19, 0.20, 0.21)   # lighter machined faces
    RED   = (0.80, 0.16, 0.13)   # red anodized
    RED2  = (0.86, 0.22, 0.18)   # lighter red highlight
    BLACK = (0.05, 0.05, 0.06)   # knobs / rubber
    BOLT  = (0.45, 0.47, 0.50)   # bright metal bolts
    METAL = (0.55, 0.57, 0.60)   # bright machined metal (axes)
    GLASS = (0.30, 0.55, 0.85)   # bubble level fluid
    WHITE = (0.84, 0.86, 0.88)   # label / scale ticks

    def add(geom, col, R=None, t=None):
        P, N = geom
        if R is not None or t is not None:
            P, N = transform(P, N, R=R, t=t)
        parts.append((P, N, col))

    def ring_of_bolts(n, radius, center, axis, br=0.16, bh=0.30, col=BOLT, phase=0.0):
        """n bolt heads on a circle, around the given local axis ('x','y','z')."""
        for k in range(n):
            a = phase + 2 * math.pi * k / n
            ca, sa = math.cos(a), math.sin(a)
            if axis == 'z':
                off = (radius * ca, radius * sa, 0.0); R = None
            elif axis == 'x':
                # bolt cylinders point along +X, arranged in y-z circle
                off = (0.0, radius * ca, radius * sa); R = rotmat('y', 90)
            else:  # 'y'
                off = (radius * ca, 0.0, radius * sa); R = rotmat('x', -90)
            t = (center[0] + off[0], center[1] + off[1], center[2] + off[2])
            add(cylinder(br, br, bh, seg=16), col, R=R, t=t)

    # =====================================================================
    # 1) LATITUDE BASE (纬度座) — RED. z roughly [-3, 3], wedge tilted ~50deg.
    #    Bottom (tripod) face tilted about X; altitude knob toward -Y;
    #    curved altitude scale faces +X.
    # =====================================================================
    LAT = 50.0  # wedge tilt angle (deg) about X

    # -- tripod mounting foot: a flat slab whose bottom is tilted ~50deg about X
    #    (so it lands horizontal once the polar axis is aimed at the pole).
    #    Kept compact so the tilted corners stay within z>=-3.
    foot = box(5.6, 3.6, 1.0)
    Rfoot = rotmat('x', -LAT)
    # center the slab on its own mid-plane before tilting, then place.
    fpP, fpN = transform(*foot, t=(0.0, 0.0, -0.5))    # center thickness on z=0
    fpP, fpN = transform(fpP, fpN, R=Rfoot, t=(0.0, 0.5, -1.15))
    parts.append((fpP, fpN, RED))
    # darker rubber/contact pads on the underside corners (decorative)
    for sx in (-1.9, 1.9):
        for sy in (-1.2, 1.2):
            pad = cylinder(0.45, 0.45, 0.26, seg=20)
            pp, pn = transform(*pad, t=(0.0, 0.0, -0.26))
            pp, pn = transform(pp, pn, R=Rfoot, t=(sx, sy + 0.5, -1.15))
            parts.append((pp, pn, BLACK))

    # -- two upright side cheeks of the latitude cradle (body pivots between).
    #    Red, rising from the foot; curved scale on the +X cheek.
    for sx in (-2.4, 2.4):
        cheek = box(0.85, 5.0, 4.4)
        add(cheek, RED, t=(sx, -0.4, -1.9))
    # front/back web connecting the cheeks low down
    web = box(4.8, 1.1, 2.8)
    add(web, RED2, t=(0.0, -2.6, -1.9))

    # -- curved ALTITUDE scale on the +X cheek (a curved red plate w/ white ticks)
    scale = tube(3.3, 2.9, 0.65, seg=48)
    Rsc = rotmat('y', 90)  # tube axis (+Z) -> +X; ring lies facing +X
    add(scale, RED2, R=Rsc, t=(2.85, -0.4, 0.35))
    # white tick marks along the curved scale (small radial boxes)
    for k in range(11):
        ang = math.radians(-56 + k * 11.0)
        rr = 3.05
        ty = -0.4 + rr * math.cos(ang)
        tz = 0.35 + rr * math.sin(ang)
        tick = box(0.10, 0.09, 0.35)
        add(tick, WHITE, R=rotmat('x', math.degrees(ang)), t=(2.95, ty, tz))

    # -- big knurled ALTITUDE adjustment bolt at the BACK, pointing toward -Y.
    Ralt = rotmat('x', -90)  # cylinder +Z -> -Y
    # knurled knob body
    add(cylinder(0.85, 0.85, 1.5, seg=32), BLACK, R=Ralt, t=(0.0, -3.0, 0.2))
    add(cylinder(0.95, 0.95, 0.4, seg=32), BLACK, R=Ralt, t=(0.0, -4.5, 0.2))   # outer knurl flange
    add(cylinder(0.3, 0.3, 1.2, seg=20), METAL, R=Ralt, t=(0.0, -3.0, 0.2))     # threaded shaft toward body
    # small red collar where shaft meets cradle
    add(tube(0.5, 0.32, 0.3, seg=24), RED, R=Ralt, t=(0.0, -2.7, 0.2))

    # -- azimuth-adjust bolts on the sides (two small knurled bolts, +/-X)
    for sx, ax in ((2.45, 1), (-2.45, -1)):
        Razi = rotmat('y', 90 * ax)
        add(cylinder(0.4, 0.4, 0.45, seg=24), BLACK, R=Razi, t=(sx, -2.2, -1.3))
        add(cylinder(0.18, 0.18, 0.45, seg=16), METAL, R=Razi, t=(sx, -2.2, -1.3))

    # =====================================================================
    # 2) MAIN BODY (方形本体) — RA / polar-axis strain-wave housing.
    #    Rounded-rectangular housing along +Z, z in [3, 17]. BLACK graphite.
    # =====================================================================
    BW, BD = 5.3, 6.0      # body cross-section (x, y)
    Z0, Z1 = 3.0, 17.0
    BL = Z1 - Z0

    # core housing (slightly inset main block)
    add(box(BW, BD, BL), BODY, t=(0.0, 0.0, Z0))
    # lighter machined "shoulder" plates top & bottom of the body
    add(box(BW + 0.5, BD + 0.5, 1.0), BODY2, t=(0.0, 0.0, Z0))         # bottom collar
    add(box(BW + 0.5, BD + 0.5, 1.2), BODY2, t=(0.0, 0.0, Z1 - 1.2))   # top collar

    # rounded edges: vertical fillet cylinders at the 4 body corners
    cr = 0.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = sx * (BW / 2 - cr)
            cy = sy * (BD / 2 - cr)
            add(cylinder(cr, cr, BL, seg=24), BODY, t=(cx, cy, Z0))

    # machined bevel strips down the long faces (lighter) for "machined" look
    for sx, R in ((BW/2 + 0.02, rotmat('y', 90)), (-BW/2 - 0.02, rotmat('y', -90))):
        strip = box(BL - 1.0, BD - 1.4, 0.18)
        add(strip, BODY2, R=R, t=(sx, 0.0, Z0 + BL/2))
    # front (+Y) and back (-Y) recessed machined panels
    for sy, R in ((BD/2 + 0.02, rotmat('x', -90)), (-BD/2 - 0.02, rotmat('x', 90))):
        panel = box(BW - 1.2, BL - 2.0, 0.18)
        add(panel, BODY2, R=R, t=(0.0, sy, Z0 + BL/2))

    # -- AM5 label panel on the +Y face (light recessed plate, lower-mid)
    add(box(3.6, 1.7, 0.12), BODY2, R=rotmat('x', -90), t=(0.0, BD/2 + 0.10, 9.5))
    # red AM5 accent bar across the label
    add(box(3.2, 0.32, 0.10), RED, R=rotmat('x', -90), t=(0.0, BD/2 + 0.16, 9.95))
    # three white "AM5"-ish stripes (decorative)
    for sx in (-0.9, 0.0, 0.9):
        add(box(0.45, 0.7, 0.08), WHITE, R=rotmat('x', -90), t=(sx, BD/2 + 0.16, 9.1))

    # -- ports / power panel on the -Y face (recessed dark plate + connectors)
    add(box(2.6, 2.0, 0.14), BLACK, R=rotmat('x', 90), t=(0.9, -BD/2 - 0.10, 6.0))
    # round connector ports
    for sx in (0.2, 0.9, 1.6):
        add(cylinder(0.28, 0.28, 0.22, seg=20), METAL, R=rotmat('x', 90), t=(sx, -BD/2 - 0.12, 6.6))
    # rectangular USB/port
    add(box(0.8, 0.4, 0.18), BODY2, R=rotmat('x', 90), t=(0.9, -BD/2 - 0.12, 5.4))

    # -- bubble level on the -Y face, near the top
    add(cylinder(0.55, 0.55, 0.22, seg=28), BLACK, R=rotmat('x', 90), t=(-1.6, -BD/2 - 0.10, 6.2))
    add(disk(0.40, seg=28, z=0.0, up=1.0), GLASS, R=rotmat('x', 90), t=(-1.6, -BD/2 - 0.30, 6.2))
    add(tube(0.42, 0.30, 0.12, seg=28), BODY2, R=rotmat('x', 90), t=(-1.6, -BD/2 - 0.31, 6.2))

    # =====================================================================
    # 3a) RA AXIS OUTPUT (赤经轴) — polar axis exits the TOP of the body (+Z).
    #     Carries the Dec assembly. Metal hub + red accent ring + 6-bolt cap.
    # =====================================================================
    # RA output flange rising out of the body top collar (the polar-axis output).
    add(cylinder(2.55, 2.45, 0.6, seg=56), BODY2, t=(0.0, 0.0, 17.0))
    # red accent ring on the RA output
    add(tube(2.55, 2.15, 0.45, seg=56), RED, t=(0.0, 0.0, 17.25))
    # RA end-cap disk with 6-bolt circle (top of mount, z<=18)
    add(cylinder(2.35, 2.35, 0.4, seg=56), BODY2, t=(0.0, 0.0, 17.45))
    ring_of_bolts(6, 1.55, (0.0, 0.0, 17.7), 'z', br=0.15, bh=0.14, col=BOLT)
    # central RA bolt
    add(cylinder(0.42, 0.42, 0.18, seg=20), BOLT, t=(0.0, 0.0, 17.7))

    # DEC carrier (赤纬头座): the elbow that carries the perpendicular Dec
    # gearbox. It is bolted on the RA output and wraps the upper body region;
    # the Dec axis runs through it at z~15.3, projecting toward +X.
    add(box(5.2, 5.4, 4.0), BODY, t=(0.0, 0.0, 13.3))      # dec carrier block (upper body)
    add(box(5.5, 5.6, 0.7), BODY2, t=(0.0, 0.0, 16.3))     # lighter cap plate under RA flange
    # rounded carrier shoulder toward +X where the Dec barrel exits
    for sy in (-1, 1):
        add(cylinder(0.5, 0.5, 4.0, seg=20), BODY, t=(2.6 - 0.5, sy * (2.7 - 0.5), 13.3))

    # =====================================================================
    # 3b) DEC AXIS (赤纬轴) — thick cylindrical harmonic gearbox along +X,
    #     at the TOP of the body (z ~ 15.5), extends to x ~ +8.
    # =====================================================================
    DECZ = 15.3
    Rdec = rotmat('y', 90)   # cylinder +Z -> +X
    # large Dec gearbox barrel
    add(cylinder(2.55, 2.55, 6.6, seg=60), BODY, R=Rdec, t=(1.4, 0.0, DECZ))
    # lighter machined band near the body side
    add(tube(2.6, 2.3, 0.9, seg=60), BODY2, R=Rdec, t=(1.7, 0.0, DECZ))
    # red accent ring partway out
    add(tube(2.62, 2.25, 0.6, seg=60), RED, R=Rdec, t=(5.4, 0.0, DECZ))
    # Dec end hub (metal) at x ~ 8 with 6-bolt circle facing +X
    add(cylinder(2.35, 2.35, 0.9, seg=60), BODY2, R=Rdec, t=(8.0 - 0.0, 0.0, DECZ))
    add(disk(2.3, seg=60, up=1.0), BODY2, R=Rdec, t=(8.9, 0.0, DECZ))
    ring_of_bolts(6, 1.5, (8.55, 0.0, DECZ), 'x', br=0.15, bh=0.2, col=BOLT)
    add(cylinder(0.42, 0.42, 0.22, seg=20), BOLT, R=Rdec, t=(8.55, 0.0, DECZ))

    # =====================================================================
    # 4) SADDLE / DOVETAIL CLAMP (鞍座) — RED, at +X end of Dec axis (~x=6.5).
    #    Dec=90 home: slot runs ALONG +Z, OPENS toward +Y.
    # =====================================================================
    SX, SY, SZ = 6.4, 0.0, 15.3   # saddle CENTER (slot center)
    SL = 5.0                       # saddle length along the slot (+Z)
    z_lo = SZ - SL / 2.0           # 12.8
    # main red saddle body: block spanning the slot length (+Z), width in x,
    # rising in +Y. The dovetail slot is the gap between the two jaws.
    add(box(3.4, 2.0, SL), RED, t=(SX, SY - 0.7, z_lo))        # saddle base body
    # darker mounting base where saddle bolts onto the Dec output hub (-Y side)
    add(box(3.0, 1.2, SL - 0.6), BODY2, t=(SX, SY - 1.4, z_lo + 0.3))
    # two raised jaw rails forming the Vixen/Losmandy dovetail slot.
    # Slot runs along +Z and OPENS toward +Y; jaws sit on +/-X sides.
    for sx in (-1, 1):
        jaw = box(0.95, 1.7, SL)
        add(jaw, RED, t=(SX + sx * 1.15, SY + 0.6, z_lo))
    # angled dovetail lips (machined metal) leaning IN over the +Y-opening slot
    for sx in (-1, 1):
        lip = box(0.65, 0.45, SL - 0.4)
        Rlip = rotmat('z', -sx * 24)   # tilt the lip so its inner face overhangs the slot
        add(lip, BODY2, R=Rlip, t=(SX + sx * 1.0, SY + 1.35, z_lo + 0.2))

    # big clamp KNOB on the side (-X side), pointing -X (handle to tighten the jaw)
    Rknob = rotmat('y', -90)  # cylinder +Z -> -X
    add(cylinder(0.85, 0.85, 1.3, seg=32), BLACK, R=Rknob, t=(SX - 1.75, SY + 0.2, SZ - 0.6))
    add(cylinder(0.98, 0.9, 0.45, seg=32), BLACK, R=Rknob, t=(SX - 3.05, SY + 0.2, SZ - 0.6))  # knurl flange
    add(cylinder(0.28, 0.28, 0.9, seg=16), METAL, R=Rknob, t=(SX - 1.75, SY + 0.2, SZ - 0.6))  # shaft
    # red collar at knob base
    add(tube(0.55, 0.3, 0.28, seg=24), RED2, R=Rknob, t=(SX - 1.7, SY + 0.2, SZ - 0.6))

    # safety screw (small, top of +X jaw, pointing +Y)
    add(cylinder(0.24, 0.24, 0.8, seg=16), BOLT, R=rotmat('x', -90), t=(SX + 1.15, SY + 1.6, SZ + 1.1))
    add(cylinder(0.36, 0.36, 0.22, seg=16), BLACK, R=rotmat('x', -90), t=(SX + 1.15, SY + 2.2, SZ + 1.1))

    return parts