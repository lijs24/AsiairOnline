def build_part(C):
    import numpy as np, math
    parts = []

    # ---- palette ----
    GRAPHITE   = (0.12, 0.13, 0.14)   # body dark
    MACHINED   = (0.19, 0.20, 0.21)   # lighter machined faces
    RED        = (0.80, 0.16, 0.13)   # anodized red
    BLACK_KNOB = (0.05, 0.05, 0.06)   # knobs
    BOLT       = (0.45, 0.47, 0.50)   # bright metal bolts
    GLASS      = (0.30, 0.55, 0.85)   # bubble level glass
    DARKRED    = (0.62, 0.12, 0.10)   # red shadow detail
    SILVER     = (0.55, 0.57, 0.60)   # bright knurled metal

    SEG = 56  # generous segments for GPU render

    def add(geo, color, R=None, t=None):
        P, N = geo
        if R is not None or t is not None:
            P, N = transform(P, N, R, t)
        parts.append((P, N, color))

    # helper: a bolt circle of small cylindrical bolt heads on a plane facing +/-axis
    def bolt_circle(n, radius, head_r, head_h, center, axis='z', color=BOLT, phase=0.0):
        if axis == 'z':
            base_R = None
        elif axis == 'x':
            base_R = rotmat('y', 90)
        elif axis == 'y':
            base_R = rotmat('x', -90)
        for k in range(n):
            a = phase + 2*math.pi*k/n
            if axis == 'z':
                off = np.array([radius*math.cos(a), radius*math.sin(a), 0.0])
            elif axis == 'x':
                off = np.array([0.0, radius*math.cos(a), radius*math.sin(a)])
            else:  # y
                off = np.array([radius*math.cos(a), 0.0, radius*math.sin(a)])
            geo = cylinder(head_r, head_r, head_h, seg=14)
            add(geo, color, base_R, np.array(center) + off)

    # =====================================================================
    # 1) LATITUDE BASE (RED)  — bottom, z roughly [-3, 3], wedge tilted ~50deg
    #    Bottom (tripod) face tilted ~50deg about X. Altitude knob toward -Y,
    #    curved scale faces +X.
    # =====================================================================
    LAT = 50.0  # degrees

    # -- Tilted tripod mounting foot plate (bottom face inclined ~50deg about X) --
    foot = box(5.6, 4.6, 1.3)            # x,y,d
    Rtilt = rotmat('x', LAT)
    add(foot, RED, Rtilt, (0.0, 0.7, -1.1))

    # central pillar / saddle that rises to support the body pivot (top ~z=2.6)
    pillar = box(5.6, 5.4, 4.2)
    add(pillar, RED, None, (0.0, 0.0, -1.6))
    # machined top pad where body pivots
    toppad = box(5.2, 4.8, 0.5)
    add(toppad, MACHINED, None, (0.0, 0.0, 2.6))

    # two upright "cheek" side plates that hold the polar pivot axle (fork look)
    for sx in (-1, +1):
        cheek = box(0.8, 4.6, 4.8)
        add(cheek, RED, None, (sx*2.6, 0.2, -1.6))

    # polar pivot axle (the body rotates about this X axis when setting latitude)
    axle = cylinder(0.55, 0.55, 5.6, seg=SEG)
    add(axle, SILVER, rotmat('y', 90), (-2.8, 0.2, 1.0))
    # axle end caps red (kept within +/-3.0 in x)
    for sx in (-1, +1):
        cap = cylinder(0.8, 0.8, 0.3, seg=24)
        if sx > 0:
            add(cap, RED, rotmat('y', -90), (2.8, 0.2, 1.0))
        else:
            add(cap, RED, rotmat('y', 90), (-2.8, 0.2, 1.0))

    # curved altitude scale — faces +X. Thin curved arc band on the +X cheek,
    # centered on the polar pivot (x=2.7, z=1.0) so it reads as an altitude arc.
    scale = tube(2.6, 2.15, 0.30, seg=SEG)
    add(scale, MACHINED, rotmat('y', 90), (2.7, 0.2, 1.0))
    scale2 = tube(2.55, 2.25, 0.16, seg=SEG)
    add(scale2, SILVER, rotmat('y', 90), (2.9, 0.2, 1.0))

    # big knurled ALTITUDE adjustment bolt at the BACK, pointing toward -Y.
    alt_knob = cylinder(1.4, 1.4, 1.7, seg=SEG)
    add(alt_knob, BLACK_KNOB, rotmat('x', 90), (0.0, -3.6, -0.8))
    alt_ring = tube(1.45, 1.25, 0.9, seg=SEG)
    add(alt_ring, SILVER, rotmat('x', 90), (0.0, -3.4, -0.8))
    alt_shaft = cylinder(0.42, 0.42, 1.9, seg=28)
    add(alt_shaft, BOLT, rotmat('x', 90), (0.0, -2.0, -0.8))

    # azimuth-adjust bolts on the SIDES (two opposing, along X), small black knobs
    for sx in (-1, +1):
        az = cylinder(0.52, 0.52, 0.55, seg=28)
        add(az, BLACK_KNOB, rotmat('y', 90*sx), (sx*2.45, 1.4, -2.0))
        azs = cylinder(0.22, 0.22, 0.55, seg=20)
        add(azs, BOLT, rotmat('y', 90*sx), (sx*2.0, 1.4, -2.0))

    # =====================================================================
    # 2) MAIN BODY (square/rounded-rectangular housing) — RA strain-wave box.
    #    Runs along +Z, z in [3, 17]. Dark graphite. RA/polar axis = +Z thru center.
    # =====================================================================
    BODY_W = 6.0   # x  (RA axis through center x=0)
    BODY_H = 6.6   # y  (roughly square cross-section)
    BODY_Z0 = 3.0
    BODY_Z1 = 17.0
    BODY_D = BODY_Z1 - BODY_Z0

    # core housing
    body = box(BODY_W, BODY_H, BODY_D)
    add(body, GRAPHITE, None, (0.0, 0.0, BODY_Z0))

    # rounded corner fillets: add quarter-cylinders at the 4 vertical edges
    cr = 1.0
    corners = [(+1,+1),(+1,-1),(-1,+1),(-1,-1)]
    for sx, sy in corners:
        cyl = cylinder(cr, cr, BODY_D, seg=20)
        add(cyl, GRAPHITE, None, (sx*(BODY_W/2-cr), sy*(BODY_H/2-cr), BODY_Z0))

    # machined bevel faces: lighter front/back plates inset slightly
    front_plate = box(BODY_W*0.82, 0.25, BODY_D*0.82)
    add(front_plate, MACHINED, None, (0.0, BODY_H/2-0.02, BODY_Z0+BODY_D*0.09))
    back_plate = box(BODY_W*0.82, 0.25, BODY_D*0.82)
    add(back_plate, MACHINED, None, (0.0, -BODY_H/2+0.02, BODY_Z0+BODY_D*0.09))

    # AM5 label panel — on the +Y front face, recessed lighter panel
    label = box(4.2, 0.18, 2.0)
    add(label, MACHINED, None, (0.0, BODY_H/2+0.10, BODY_Z0 + 8.0))
    label_in = box(3.4, 0.12, 1.2)
    add(label_in, GRAPHITE, None, (0.0, BODY_H/2+0.16, BODY_Z0 + 8.0))

    # ports / power panel on the -Y back face, lower region (recessed lighter panel)
    ports = box(3.4, 0.22, 2.6)
    add(ports, MACHINED, None, (0.0, -BODY_H/2-0.06, BODY_Z0 + 2.6))
    for (px, pz, pr) in [(-1.0,1.4,0.45),(0.2,1.4,0.45),(1.1,2.8,0.35),(-1.0,3.6,0.30)]:
        hole = cylinder(pr, pr, 0.3, seg=20)
        add(hole, BLACK_KNOB, rotmat('x', 90), (px, -BODY_H/2-0.12, BODY_Z0 + pz))

    # bubble level on the +Y front face near the bottom
    bub_housing = cylinder(0.7, 0.7, 0.25, seg=SEG)
    add(bub_housing, MACHINED, rotmat('x', -90), (1.9, BODY_H/2+0.05, BODY_Z0 + 1.4))
    bub_glass = cylinder(0.5, 0.5, 0.18, seg=SEG)
    add(bub_glass, GLASS, rotmat('x', -90), (1.9, BODY_H/2+0.12, BODY_Z0 + 1.4))

    # body-to-base joint collar at bottom of body
    collar = cylinder(2.9, 2.9, 0.8, seg=SEG)
    add(collar, MACHINED, None, (0.0, 0.0, BODY_Z0 - 0.4))

    # =====================================================================
    # 3) RA AXIS OUTPUT (top of body, polar axis exits along +Z) carrying the
    #    Dec assembly; + DEC AXIS perpendicular (along +X).
    # =====================================================================
    # RA output: polar axis exits the TOP of the body. Short machined boss collar
    # sits flush at the body top (z=17) that the Dec elbow mounts onto.
    ra_boss = cylinder(2.85, 2.65, 0.7, seg=SEG)
    add(ra_boss, MACHINED, None, (0.0, 0.0, BODY_Z1 - 0.5))
    ra_ring = tube(2.8, 2.4, 0.35, seg=SEG)                   # red accent ring
    add(ra_ring, RED, None, (0.0, 0.0, BODY_Z1 - 0.45))
    # RA gearbox REAR bearing cover with 6-bolt circle on the BOTTOM of the body
    # (faces the latitude base; classic AM5 RA bearing cover disc).
    ra_cap = cylinder(2.85, 2.85, 0.5, seg=SEG)
    add(ra_cap, GRAPHITE, None, (0.0, 0.0, BODY_Z0 - 0.5))
    ra_cap_ring = tube(2.9, 2.45, 0.3, seg=SEG)
    add(ra_cap_ring, RED, None, (0.0, 0.0, BODY_Z0 - 0.5))
    for k in range(6):
        a = 2*math.pi*k/6
        off = (2.2*math.cos(a), 2.2*math.sin(a), 0.0)
        bh = cylinder(0.22, 0.22, 0.24, seg=14)
        add(bh, BOLT, None, (off[0], off[1], BODY_Z0 - 0.74))

    # The Dec housing block (elbow) connects RA(+Z) to Dec(+X). Graphite block.
    DEC_Z = 15.0  # center height of the dec axis
    ELB_Z0 = BODY_Z1 - 3.6   # 13.4
    ELB_D  = 4.0             # top at 17.4 (under 18)
    elbow = box(5.4, 6.4, ELB_D)
    add(elbow, GRAPHITE, None, (1.2, 0.0, ELB_Z0))
    for sy in (-1, +1):
        eb = cylinder(0.9, 0.9, ELB_D, seg=18)
        add(eb, GRAPHITE, None, (1.2 + 2.7 - 0.9, sy*(3.2 - 0.9), ELB_Z0))

    # ----- DEC AXIS along +X, centered at z=DEC_Z, extends to x~+8 -----
    DEC_X0 = 1.6   # where it leaves the elbow
    DEC_R = 2.6
    dec_barrel = cylinder(DEC_R, DEC_R, 6.0, seg=SEG)
    add(dec_barrel, GRAPHITE, rotmat('y', 90), (DEC_X0, 0.0, DEC_Z))
    dec_band = tube(DEC_R+0.05, DEC_R-0.25, 1.2, seg=SEG)
    add(dec_band, MACHINED, rotmat('y', 90), (DEC_X0+2.2, 0.0, DEC_Z))
    dec_red = tube(DEC_R+0.1, DEC_R-0.2, 0.6, seg=SEG)            # red accent ring (shoulder)
    add(dec_red, RED, rotmat('y', 90), (DEC_X0+0.2, 0.0, DEC_Z))
    dec_red2 = tube(DEC_R+0.08, DEC_R-0.2, 0.6, seg=SEG)         # red accent ring (outboard)
    add(dec_red2, RED, rotmat('y', 90), (DEC_X0+5.4, 0.0, DEC_Z))
    dec_cap = cylinder(DEC_R-0.15, DEC_R-0.15, 0.5, seg=SEG)
    add(dec_cap, GRAPHITE, rotmat('y', 90), (DEC_X0+6.0, 0.0, DEC_Z))
    bolt_circle(6, 1.7, 0.22, 0.30, (DEC_X0+6.4, 0.0, DEC_Z), axis='x', color=BOLT)
    dec_hub = cylinder(0.6, 0.6, 0.35, seg=28)
    add(dec_hub, SILVER, rotmat('y', 90), (DEC_X0+6.4, 0.0, DEC_Z))

    # =====================================================================
    # 4) SADDLE / DOVETAIL CLAMP (RED) on the +X end of the Dec axis.
    #    Dec=90 home: dovetail SLOT runs ALONG +Z, OPENS toward +Y.
    # =====================================================================
    SAD_X = 6.3
    SAD_Z = DEC_Z
    SAD_XW = 4.4   # x width of saddle body (clamp jaws)
    SAD_ZL = 5.6   # z length (along slot)
    SAD_YD = 2.8   # y depth (toward +Y)
    SAD_ZC = SAD_Z - 0.4   # slot center z, shifted down to stay under z=18

    sad_body = box(SAD_XW, SAD_YD, SAD_ZL)
    add(sad_body, RED, None, (SAD_X, 0.3, SAD_ZC - SAD_ZL/2))

    # Dovetail V-slot opening toward +Y: two angled jaw rails on the +Y face
    # running along Z, forming a V groove with the mouth at +Y.
    SLOT_BASE_Y = 0.3 + SAD_YD/2   # +Y face of the body
    for sx in (-1, +1):
        rail = box(0.85, 1.1, SAD_ZL)
        Rr = rotmat('z', -16*sx)   # tilt inner face -> dovetail V
        add(rail, RED, Rr, (SAD_X + sx*1.35, SLOT_BASE_Y + 0.55, SAD_ZC - SAD_ZL/2))
    slot_floor = box(2.2, 0.45, SAD_ZL)   # floor of the slot
    add(slot_floor, MACHINED, None, (SAD_X, SLOT_BASE_Y + 0.22, SAD_ZC - SAD_ZL/2))

    # big clamp KNOB on the -X side of saddle - black knurled
    knob = cylinder(1.2, 1.2, 1.5, seg=SEG)
    add(knob, BLACK_KNOB, rotmat('y', -90), (SAD_X - SAD_XW/2 - 0.2, 1.0, SAD_ZC - 1.2))
    knob_knurl = tube(1.25, 1.0, 0.9, seg=SEG)
    add(knob_knurl, SILVER, rotmat('y', -90), (SAD_X - SAD_XW/2 - 0.9, 1.0, SAD_ZC - 1.2))
    knob_shaft = cylinder(0.38, 0.38, 1.3, seg=24)
    add(knob_shaft, BOLT, rotmat('y', -90), (SAD_X - SAD_XW/2 - 0.2, 1.0, SAD_ZC - 1.2))

    # safety screw on the +Z end of the saddle
    safety_top = SAD_ZC + SAD_ZL/2
    safety = cylinder(0.4, 0.4, 0.45, seg=24)
    add(safety, BLACK_KNOB, None, (SAD_X + 1.2, 1.6, safety_top - 0.15))
    safety_h = cylinder(0.55, 0.55, 0.25, seg=20)
    add(safety_h, BLACK_KNOB, None, (SAD_X + 1.2, 1.6, safety_top + 0.3))

    # red accent rim atop the saddle (top edge along +Y)
    sad_rim = box(SAD_XW, 0.4, 0.5)
    add(sad_rim, DARKRED, None, (SAD_X, SLOT_BASE_Y + 1.2, SAD_ZC + SAD_ZL/2 - 0.5))

    return parts