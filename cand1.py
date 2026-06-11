def build_part(C):
    import numpy as np, math
    parts = []

    # ---------- palette ----------
    BODY  = (0.12, 0.13, 0.14)   # dark graphite housing
    BODY2 = (0.19, 0.20, 0.21)   # lighter machined faces
    RED   = (0.80, 0.16, 0.13)   # red anodized
    RED2  = (0.87, 0.23, 0.18)   # brighter red highlight
    BLACK = (0.05, 0.05, 0.06)   # knobs / rubber
    BOLT  = (0.45, 0.47, 0.50)   # bright metal bolts
    METAL = (0.56, 0.58, 0.61)   # bright machined metal (shafts/axes)
    GLASS = (0.30, 0.55, 0.85)   # bubble level fluid
    WHITE = (0.85, 0.86, 0.88)   # labels / scale ticks

    SEG = 56

    def add(geom, col, R=None, t=None):
        P, N = geom
        if R is not None or t is not None:
            P, N = transform(P, N, R=R, t=t)
        parts.append((P, N, col))

    def ring_of_bolts(n, radius, center, axis, br=0.16, bh=0.20, col=BOLT, phase=0.0):
        """n cylindrical bolt heads on a circle, the bolts pointing along +axis."""
        for k in range(n):
            a = phase + 2*math.pi*k/n
            ca, sa = math.cos(a), math.sin(a)
            if axis == 'z':
                off = (radius*ca, radius*sa, 0.0); R = None
            elif axis == 'x':
                off = (0.0, radius*ca, radius*sa); R = rotmat('y', 90)
            else:  # 'y'
                off = (radius*ca, 0.0, radius*sa); R = rotmat('x', -90)
            t = (center[0]+off[0], center[1]+off[1], center[2]+off[2])
            add(cylinder(br, br, bh, seg=16), col, R=R, t=t)

    # =================================================================
    # 1) LATITUDE BASE (纬度座) — RED, bottom of mount, z ~ [-3, 3].
    #    A cradle/wedge whose tripod bottom face is tilted ~50deg about X.
    #    Altitude knob points -Y, curved altitude scale faces +X.
    # =================================================================
    LAT = 50.0
    Rfoot = rotmat('x', -LAT)   # tilt bottom face about X

    # -- tripod mounting foot: a wide slab whose underside is tilted ~50 deg.
    add(box(7.4, 5.0, 1.3), RED, R=Rfoot, t=(0.0, 0.4, -1.2))
    # bright machined ring on top of the foot (azimuth bearing seat)
    add(cylinder(2.7, 2.7, 0.32, seg=SEG), BODY2, R=Rfoot, t=(0.0, 0.4, -0.6))
    # three black rubber feet on the underside corners
    for (fx, fy) in [(0.0, -1.9), (-2.4, 1.6), (2.4, 1.6)]:
        add(cylinder(0.50, 0.50, 0.28, seg=22), BLACK, R=Rfoot, t=(fx, fy + 0.4, -1.35))

    # -- two upright RED cheeks of the latitude cradle; the body pivots between.
    for sx in (-3.0, 3.0):
        add(box(1.0, 5.4, 4.4), RED, t=(sx, -0.5, -2.0))
    # rear web tying the cheeks together (where altitude screw pushes)
    add(box(5.2, 1.3, 2.8), RED2, t=(0.0, -2.8, -2.0))
    # front low web
    add(box(5.2, 1.0, 1.6), RED, t=(0.0, 2.4, -2.0))

    # -- curved ALTITUDE scale on the +X cheek (curved red plate + white ticks).
    #    Centered up at z~0.6 so the ring stays within z>=-3; ticks face +X.
    Rsc = rotmat('y', 90)  # tube axis -> +X (annulus lies facing +X)
    SC_CY, SC_CZ, SC_R = -0.3, 0.7, 3.3
    add(tube(SC_R, SC_R - 0.55, 0.85, seg=SEG), RED2, R=Rsc, t=(3.55, SC_CY, SC_CZ))
    for k in range(11):
        ang = math.radians(-50 + k*10.0)
        ty = SC_CY + (SC_R - 0.05)*math.cos(ang)
        tz = SC_CZ + (SC_R - 0.05)*math.sin(ang)
        add(box(0.12, 0.10, 0.45), WHITE, R=rotmat('x', math.degrees(ang)), t=(3.95, ty, tz))

    # -- big knurled ALTITUDE adjustment bolt at BACK, pointing -Y.
    Ralt = rotmat('x', -90)  # cylinder +Z -> -Y
    add(cylinder(0.35, 0.35, 1.6, seg=24), METAL, R=Ralt, t=(0.0, -3.0, 0.2))   # threaded shaft
    add(cylinder(0.95, 0.95, 1.6, seg=32), BLACK, R=Ralt, t=(0.0, -3.6, 0.2))   # knurled body
    add(cylinder(1.06, 1.06, 0.45, seg=32), BLACK, R=Ralt, t=(0.0, -5.2, 0.2))  # outer knurl flange
    add(tube(0.55, 0.36, 0.30, seg=24), RED, R=Ralt, t=(0.0, -2.95, 0.2))       # red collar

    # -- azimuth-adjust bolts flanking the altitude screw, pointing -Y (push-pull pair)
    for sx in (-1.4, 1.4):
        add(cylinder(0.40, 0.40, 0.55, seg=24), BLACK, R=Ralt, t=(sx, -2.7, -0.7))
        add(cylinder(0.16, 0.16, 0.9, seg=16), METAL, R=Ralt, t=(sx, -2.5, -0.7))

    # =================================================================
    # 2) MAIN BODY (方形本体) — RA / polar-axis strain-wave housing.
    #    Rounded-rectangular housing running along +Z, z in [3, 17].
    # =================================================================
    BW, BD = 6.4, 6.0       # body cross-section (x, y)
    Z0, Z1 = 3.0, 17.0
    BL = Z1 - Z0

    # core housing
    add(box(BW, BD, BL), BODY, t=(0.0, 0.0, Z0))
    # rounded vertical corner fillets
    cr = 0.85
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = sx*(BW/2 - cr*0.55)
            cy = sy*(BD/2 - cr*0.55)
            add(cylinder(cr, cr, BL, seg=24), BODY, t=(cx, cy, Z0))
    # lighter machined shoulder collars top & bottom
    add(box(BW + 0.3, BD + 0.3, 1.0), BODY2, t=(0.0, 0.0, Z0))
    add(box(BW + 0.3, BD + 0.3, 1.1), BODY2, t=(0.0, 0.0, Z1 - 1.1))

    # machined bevel strips on +X / -X long faces
    for sx, R in ((BW/2 + 0.02, rotmat('y', 90)), (-BW/2 - 0.02, rotmat('y', -90))):
        add(box(BL - 1.4, BD - 1.6, 0.18), BODY2, R=R, t=(sx, 0.0, Z0 + BL/2))

    # -- AM5 label panel on the +Y face (lighter recessed plate + red bar)
    add(box(3.8, 3.0, 0.12), BODY2, R=rotmat('x', -90), t=(0.0, BD/2 + 0.08, 9.6))
    add(box(3.2, 0.42, 0.10), RED, R=rotmat('x', -90), t=(0.0, BD/2 + 0.16, 10.4))   # red AM5 bar
    for sx in (-0.95, 0.0, 0.95):                                                    # white "A M 5" blocks
        add(box(0.5, 0.7, 0.08), WHITE, R=rotmat('x', -90), t=(sx, BD/2 + 0.16, 9.4))

    # -- ports / power panel on the -Y face (recessed black plate + connectors)
    add(box(2.8, 2.2, 0.14), BLACK, R=rotmat('x', 90), t=(0.7, -BD/2 - 0.08, 6.2))
    for sx in (0.0, 0.7, 1.4):
        add(cylinder(0.28, 0.28, 0.22, seg=20), METAL, R=rotmat('x', 90), t=(sx, -BD/2 - 0.10, 6.7))
    add(box(0.9, 0.45, 0.18), BODY2, R=rotmat('x', 90), t=(0.7, -BD/2 - 0.10, 5.6))   # USB/12V port

    # -- bubble level on -Y face near top
    add(cylinder(0.55, 0.55, 0.22, seg=28), BLACK, R=rotmat('x', 90), t=(-1.7, -BD/2 - 0.08, 7.0))
    add(cylinder(0.40, 0.40, 0.26, seg=28), GLASS, R=rotmat('x', 90), t=(-1.7, -BD/2 - 0.12, 7.0))
    add(tube(0.42, 0.30, 0.10, seg=28), BODY2, R=rotmat('x', 90), t=(-1.7, -BD/2 - 0.30, 7.0))

    # =================================================================
    # 3a) RA AXIS OUTPUT (赤经轴) — polar axis exits the TOP of body (+Z).
    #     metal hub + red accent ring + 6-bolt end cap.  Carries Dec elbow.
    # =================================================================
    add(cylinder(2.6, 2.55, 0.7, seg=SEG), BODY2, t=(0.0, 0.0, Z1))        # output flange
    add(tube(2.6, 2.2, 0.5, seg=SEG), RED, t=(0.0, 0.0, Z1 + 0.45))        # red accent ring
    add(cylinder(2.3, 2.3, 0.35, seg=SEG), BODY2, t=(0.0, 0.0, Z1 + 0.85)) # end cap disk
    ring_of_bolts(6, 1.55, (0.0, 0.0, Z1 + 1.2), 'z', br=0.15, bh=0.14, col=BOLT)
    add(cylinder(0.45, 0.45, 0.18, seg=20), BOLT, t=(0.0, 0.0, Z1 + 1.2))  # central RA bolt

    # =================================================================
    # 3b) DEC CARRIER ELBOW — rides on the RA output, holds the Dec gearbox.
    #     Block atop the body, offset so the Dec axis center is z ~ 15.3.
    # =================================================================
    DECZ = 15.3
    add(box(5.2, 5.6, 4.8), BODY, t=(0.3, 0.0, 12.6))        # elbow block (overlaps body top)
    add(box(5.6, 5.9, 0.7), BODY2, t=(0.3, 0.0, 16.6))       # lighter top plate
    # machined cheek on +X side of the elbow (where Dec axis exits)
    add(box(0.18, 5.0, 3.6), BODY2, R=rotmat('y', 90), t=(0.3 + 5.2/2 + 0.02, 0.0, DECZ))

    # =================================================================
    # 3c) DEC AXIS (赤纬轴) — thick cylindrical harmonic gearbox along +X,
    #     at z ~ 15.3, reaching to x ~ +8.
    # =================================================================
    Rdec = rotmat('y', 90)   # cylinder +Z -> +X
    add(cylinder(2.55, 2.55, 6.6, seg=60), BODY, R=Rdec, t=(1.4, 0.0, DECZ))   # Dec barrel
    add(tube(2.62, 2.3, 0.9, seg=60), BODY2, R=Rdec, t=(1.6, 0.0, DECZ))       # machined band (body side)
    add(tube(2.6, 2.25, 0.6, seg=60), RED, R=Rdec, t=(5.2, 0.0, DECZ))         # red accent ring (outboard)
    # Dec end hub (lighter) + outboard end cap + 6-bolt circle facing +X
    add(cylinder(2.35, 2.35, 0.9, seg=60), BODY2, R=Rdec, t=(8.0, 0.0, DECZ))
    add(disk(2.3, seg=60, up=1.0), BODY2, R=Rdec, t=(8.9, 0.0, DECZ))
    ring_of_bolts(6, 1.5, (8.55, 0.0, DECZ), 'x', br=0.15, bh=0.2, col=BOLT)
    add(cylinder(0.42, 0.42, 0.22, seg=20), BOLT, R=Rdec, t=(8.55, 0.0, DECZ))  # center bolt

    # =================================================================
    # 4) SADDLE / DOVETAIL CLAMP (鞍座) — RED, on the Dec axis at +X end (~x=6.5).
    #    Dec=90 home position: dovetail SLOT runs ALONG +Z, OPENS toward +Y.
    #    A scope (optical axis +Z) with an underside dovetail drops in from +Y
    #    and ends up offset on the +Y side.
    # =================================================================
    SX, SY, SZ = 6.5, 0.0, 15.3       # saddle reference (center of the dec mount face region)
    SLOT_LEN = 6.0                    # slot length along +Z
    Zs = SZ - SLOT_LEN/2.0            # slot z-start

    # -- saddle base block (red): bolts onto the Dec hub, body of the clamp.
    #    Spans X (width across slot), Y (height up to the +Y opening), Z (slot length).
    add(box(3.4, 2.2, SLOT_LEN), RED, t=(SX, SY - 0.5, Zs))           # main red saddle body
    add(box(3.1, 1.0, SLOT_LEN - 0.2), BODY2, t=(SX, SY - 1.4, Zs + 0.1))  # darker mounting base under it

    # -- two jaw rails forming the Vixen/Losmandy slot; slot opens +Y, runs +Z.
    #    Jaws sit on +/-X sides; the dovetail channel is the +Y-open gap between them.
    for sx in (-1, 1):
        add(box(0.85, 1.9, SLOT_LEN), RED, t=(SX + sx*1.15, SY + 1.05, Zs))
    # angled dovetail lips (machined) leaning inward over the slot
    for sx in (-1, 1):
        add(box(0.7, 0.45, SLOT_LEN - 0.4), BODY2, R=rotmat('z', -sx*24), t=(SX + sx*0.9, SY + 1.75, Zs + 0.2))
    # slot floor strip (recessed machined surface at the bottom of the channel)
    add(box(1.5, 0.18, SLOT_LEN - 0.6), BODY2, t=(SX, SY + 0.65, Zs + 0.3))

    # -- big clamp KNOB on the side (-X), pointing -X (graspable handle).
    Rknob = rotmat('y', -90)  # +Z -> -X
    add(cylinder(0.30, 0.30, 1.0, seg=20), METAL, R=Rknob, t=(SX - 1.7, SY + 0.4, SZ - 0.2))   # shaft
    add(cylinder(0.92, 0.92, 1.5, seg=32), BLACK, R=Rknob, t=(SX - 1.8, SY + 0.4, SZ - 0.2))   # knob body
    add(cylinder(1.04, 1.04, 0.45, seg=32), BLACK, R=Rknob, t=(SX - 3.3, SY + 0.4, SZ - 0.2))  # knurl flange
    add(tube(0.6, 0.32, 0.3, seg=24), RED2, R=Rknob, t=(SX - 1.78, SY + 0.4, SZ - 0.2))        # red collar

    # -- safety screw (small bright bolt, top of the +X jaw, pointing +Y).
    add(cylinder(0.26, 0.26, 0.85, seg=16), BOLT, R=rotmat('x', -90), t=(SX + 1.15, SY + 2.0, SZ - 1.8))
    add(cylinder(0.40, 0.40, 0.25, seg=16), BLACK, R=rotmat('x', -90), t=(SX + 1.15, SY + 2.7, SZ - 1.8))
    # -- a second safety stop at the -Z end of the slot
    add(box(1.4, 0.7, 0.4), BOLT, t=(SX, SY + 0.9, Zs - 0.4))

    return parts