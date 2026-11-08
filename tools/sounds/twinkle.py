"""twinkle.py: the Twinkle Lullaby toolkit. Needs Python 3.9+ and numpy."""

import wave

import numpy as np

RATE = 32000                       # 32 kHz: plenty for soft bells, small files
PEAK = 10 ** (-3 / 20)             # never above -3 dBFS
EFFECT_LUFS = -16.0                # momentary max (loudest 400 ms) of an effect
LOOP_LUFS = -24.0                  # integrated loudness of a music loop
SCALE = ("D", "E", "F#", "A", "B")  # D major pentatonic, the only notes allowed
rng = np.random.default_rng(0)


def seed(k):
    """Give each sound its own seeded generator, so changing one never moves another."""
    global rng
    rng = np.random.default_rng(5000 + k)


# --- notes ----------------------------------------------------------------------------

def n(note):
    """'F#5' -> Hz (A4 = 440). Refuses any note outside D major pentatonic."""
    name, octave = note[:-1], int(note[-1])
    assert name in SCALE, f"{note} is not in D major pentatonic"
    semis = {"D": -7, "E": -5, "F#": -3, "A": 0, "B": 2}[name] + 12 * (octave - 4)
    return 440.0 * 2 ** (semis / 12)


def up(note, octaves):
    """'D6', -1 -> 'D5'."""
    return note[:-1] + str(int(note[-1]) + octaves)


def between(a, b):
    """The scale notes strictly between a and b, in order from a to b."""
    ladder = [f"{x}{o}" for o in range(1, 9) for x in SCALE]
    i, j = ladder.index(a), ladder.index(b)
    return ladder[i + 1:j] if i < j else ladder[j + 1:i][::-1]


# --- shapes ---------------------------------------------------------------------------

def times(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def attack(t, seconds):
    return np.clip(t / max(seconds, 1e-4), 0, 1)


def smooth(t, a, b):
    """0 before a, 1 after b, a smoothstep between."""
    x = np.clip((t - a) / (b - a), 0, 1)
    return x * x * (3 - 2 * x)


def darken(sound, cutoff):
    """A gentle low-pass: the same note, less bright. For softness, never for volume."""
    spec = np.fft.rfft(sound)
    f = np.fft.rfftfreq(len(sound), 1 / RATE)
    roll = np.where(f > cutoff, np.exp(-((f - cutoff) / (0.6 * cutoff)) ** 2), 1.0)
    return np.fft.irfft(spec * roll, len(sound))


class Track:
    """A stereo buffer that mono sounds are placed into."""

    def __init__(self, seconds):
        self.data = np.zeros((2, int(seconds * RATE)))

    def add(self, sound, at=0.0, pan=0.0, gain=1.0):
        """`pan` is -1 (left) to 1 (right), or a curve (one value per sample) for a
        sound that travels. Equal power."""
        start = int(at * RATE)
        end = min(start + len(sound), self.data.shape[1])
        if end <= start:
            return
        k = end - start
        pan = np.broadcast_to(np.asarray(pan, float), (len(sound),))[:k]
        angle = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        part = sound[:k] * gain
        self.data[0, start:end] += part * np.cos(angle)
        self.data[1, start:end] += part * np.sin(angle)


# --- instruments (mono) ---------------------------------------------------------------

def kalimba(freq, seconds=1.0, decay=0.35):
    """A thumb-piano pluck: a round tone and a quick metallic tick (5.4x)."""
    t = times(seconds)
    tone = (np.sin(2 * np.pi * freq * t) * np.exp(-t / decay)
            + 0.35 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t / (decay * 0.12))
            + 0.15 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t / (decay * 0.5)))
    return tone * attack(t, 0.003)


def glass(note, seconds=1.5, decay=0.6):
    """A glass bell: inharmonic partials, the high ones fading first. A partial past
    half the sample rate is left out (it would fold back as a harsh alias)."""
    f = n(note)
    t = times(seconds)
    partials = ((1.0, 1.0, 1.0), (2.76, 0.4, 0.45), (5.40, 0.2, 0.25), (8.93, 0.08, 0.15))
    tone = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / (decay * d))
               for r, a, d in partials if f * r < RATE / 2)
    return tone * attack(t, 0.002)


def bell(note, seconds=1.6, decay=0.6, pluck=0.35):
    """The music box: a glass bell with a kalimba pluck inside it. The melody voice."""
    return glass(note, seconds, decay) + pluck * kalimba(n(note), seconds, decay * 0.35)


def wood(freq, seconds=0.8, decay=0.18):
    """A marimba-like knock. Always darken it (about 2200 Hz): a tock, never a click."""
    t = times(seconds)
    tone = (np.sin(2 * np.pi * freq * t) * np.exp(-t / decay)
            + 0.5 * np.sin(2 * np.pi * freq * 3.93 * t) * np.exp(-t / (decay * 0.15))
            + 0.25 * np.sin(2 * np.pi * freq * 9.8 * t) * np.exp(-t / (decay * 0.05)))
    return tone * attack(t, 0.002)


def flute(f_from, f_to, seconds, glide=0.25, vibrato=0.006):
    """A soft flute that glides from one pitch to another (smoothstep), with a slow
    vibrato that only comes in after the attack."""
    t = times(seconds)
    curve = smooth(t, 0.0, glide)
    freq = f_from + (f_to - f_from) * curve
    freq = freq * (1 + vibrato * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.3, 0, 1))
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    tone = np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.06 * np.sin(3 * phase)
    return tone * attack(t, 0.08) * np.clip((seconds - t) / 0.35, 0, 1)


def flute_pair(tr, note, seconds, at=0.0, gain=0.4, spread=0.25, vibrato=0.002, to=None,
               glide=0.25, pan=0.0):
    """Two flutes a hair apart, one on each side. The slow beat between them (about
    2 Hz at most) makes a round, living tone instead of a beep."""
    d = min(0.003, 1.1 / n(note))
    for detune, side in ((1 - d, -spread), (1 + d, spread)):
        f0 = n(note) * detune
        f1 = (n(to) if to else n(note)) * detune
        tr.add(flute(f0, f1, seconds, glide=glide, vibrato=vibrato), at, pan + side, gain)


def pad(freqs, seconds, swell=0.4, release=0.6, brightness=3):
    """Warm, soft saw-ish voices, each doubled 0.3 % sharp and flat. `brightness` is
    how many harmonics (2 or 3 here; more gets buzzy)."""
    t = times(seconds)
    tone = np.zeros_like(t)
    for f in freqs:
        for detune in (-0.003, 0.003):
            for h in range(1, brightness + 1):
                tone += np.sin(2 * np.pi * f * (1 + detune) * h * t
                               + rng.uniform(0, 6.28)) / h ** 1.6
    env = attack(t, swell) * np.clip((seconds - t) / release, 0, 1)
    return tone * env / (len(freqs) * 2)


def halo(freqs, seconds, stagger=0.35, fade_in=0.8, release=1.2):
    """A soft glow: steady flutes coming in one after another, fading out together.
    Level the whole time: no tremolo, no gating."""
    t = times(seconds)
    out = np.zeros_like(t)
    for i, f in enumerate(freqs):
        out += flute(f, f, seconds, vibrato=0.0) * smooth(t, i * stagger, i * stagger + fade_in)
    return out * np.clip((seconds - t) / release, 0, 1) / len(freqs)


def airy(seconds, low_from, low_to, high_from, high_to, voices=200):
    """Air: many quiet sines at random pitches inside a band that moves over time
    (a breath, a swish, a lid lifting). Shape it with sin(pi*s)**2."""
    t = times(seconds)
    p = t / seconds
    low = low_from * (low_to / low_from) ** p
    high = high_from * (high_to / high_from) ** p
    out = np.zeros_like(t)
    for _ in range(voices):
        f = np.exp(rng.uniform(np.log(min(low_from, low_to) * 0.7),
                               np.log(max(high_from, high_to) * 1.3)))
        inside = np.clip(np.minimum(f - low, high - f) / (0.25 * f) + 0.5, 0, 1)
        out += inside * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    return out / np.sqrt(voices)


def metal(freq, seconds, partials, decay, strike=0.25, soft=0.004):
    """A struck metal bar or gong: (ratio, level, decay share) partials and a short,
    dark mallet knock."""
    t = times(seconds)
    tone = sum(a * np.sin(2 * np.pi * freq * r * t + rng.uniform(0, 6.28))
               * np.exp(-t / (decay * d)) for r, a, d in partials if freq * r < RATE / 2 - 500)
    tone = tone * attack(t, soft)
    knock = airy(0.03, freq * 1.5, freq * 1.2, freq * 4, freq * 3, voices=60)
    knock *= np.exp(-np.arange(len(knock)) / RATE / 0.008)
    tone[:len(knock)] += strike * knock
    return tone * np.clip((seconds - t) / 0.2, 0, 1)


def saron(freq, seconds=2.2):
    """A gamelan bronze bar: a clear note with a bright ring that fades fast."""
    return metal(freq, seconds, ((1, 1, 1), (2.71, 0.32, 0.45), (4.95, 0.1, 0.2),
                                 (7.3, 0.04, 0.1)), 0.9)


def gong(freq, seconds=4.0):
    """A soft hanging gong to close a phrase: low, slow to bloom, long."""
    return metal(freq, seconds, ((1, 1, 1), (1.48, 0.3, 0.6), (2.0, 0.35, 0.7),
                                 (2.74, 0.12, 0.35), (3.8, 0.05, 0.2)), 1.6, strike=0.05, soft=0.03)


def breathy(f_from, f_to, seconds, glide=0.25, vibrato=0.003, breath=0.35, odd=False,
            chiff=0.0, swell=0.08):
    """A wooden or bamboo flute with breath around the tone. `odd` keeps only odd
    harmonics (a pipe closed at one end: pan flute, koauau); `chiff` adds a pan
    flute's little puff at the start."""
    t = times(seconds)
    freq = f_from + (f_to - f_from) * smooth(t, 0.0, glide)
    freq = freq * (1 + vibrato * np.sin(2 * np.pi * 4.6 * t) * smooth(t, 0.2, 0.6))
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    if odd:
        tone = np.sin(phase) + 0.14 * np.sin(3 * phase) + 0.05 * np.sin(5 * phase)
    else:
        tone = np.sin(phase) + 0.2 * np.sin(2 * phase) + 0.07 * np.sin(3 * phase)
    mid = np.sqrt(f_from * f_to)
    out = (tone + breath * airy(seconds, mid * 0.8, mid * 0.85, mid * 1.6, mid * 1.5, 90)
           + 0.25 * breath * airy(seconds, 1800, 2000, 5000, 4800, 80))
    if chiff:
        c = airy(0.05, mid * 2, mid * 1.6, mid * 6, mid * 5, 60)
        out[:len(c)] += chiff * c * np.sin(np.pi * np.arange(len(c)) / len(c))
    return out * attack(t, swell) * np.clip((seconds - t) / 0.3, 0, 1)


def pluck(freq, seconds, bright=4000.0, ring=2.0, dark=6):
    """A plucked string (Karplus-Strong): a burst of soft noise circling a delay line
    one period long, a little darker on each pass. `bright` sets the pluck's colour,
    `ring` the seconds to fade 60 dB, `dark` how fast it mellows (6 is a classic
    string; 4 a guzheng, 10 an oud). Runs three times faster, then resamples, so
    short strings stay in tune."""
    fast = 3 * RATE
    period = max(dark + 2, int(round(fast / freq - (dark - 1) / 2)))
    rate = freq * (period + (dark - 1) / 2)
    total = int(seconds * rate * 1.3) + period
    burst = rng.standard_normal(period)
    f = np.fft.rfftfreq(period, 1 / rate)
    burst = np.fft.irfft(np.fft.rfft(burst) * np.exp(-(f / (bright * 1.6)) ** 2), period)
    y = np.zeros(total + dark)
    y[dark:dark + period] = burst
    g = 10 ** (-3 / (freq * ring))
    for start in range(dark + period, len(y), period):
        end = min(start + period, len(y))
        acc = sum(y[start - period - j:end - period - j] for j in range(dark))
        y[start:end] = g * acc / dark
    y = y[dark:]
    count = int(seconds * RATE)
    out = np.interp(np.arange(count) * rate / RATE, np.arange(len(y)), y, right=0.0)
    out *= attack(np.arange(count) / RATE, 0.002) * np.clip((seconds - times(seconds)) / 0.2, 0, 1)
    return out / (np.abs(out).max() + 1e-12)


# --- the room -------------------------------------------------------------------------

def reverb(data, wet=0.3, seconds=1.8, damping=3.0):
    """One shared synthetic room: decaying noise, darker as it fades, partly different
    on each side so the tail is wide; 12 ms pre-delay; unity gain from 200 Hz to
    4 kHz so `wet` means what it says. The room uses its own fixed seed, so every
    sound sits in the same room."""
    r = np.random.default_rng(20261014)
    size = int(seconds * RATE)
    t = np.arange(size) / RATE
    out = np.zeros((2, data.shape[1] + size))
    shared = r.standard_normal(size)
    freqs = np.fft.rfftfreq(size, 1 / RATE)
    band = (freqs >= 200) & (freqs <= 4000)
    full = data.shape[1] + size
    for side in range(2):
        ir = (0.7 * shared + 0.7 * r.standard_normal(size)) * np.exp(-t * 6.9 / seconds)
        ir = np.fft.irfft(np.fft.rfft(ir) * np.exp(-freqs / (RATE / damping / 2)), size)
        ir[:int(0.012 * RATE)] *= np.linspace(0, 1, int(0.012 * RATE))
        ir /= np.sqrt(np.mean(np.abs(np.fft.rfft(ir)[band]) ** 2))
        conv = np.fft.irfft(np.fft.rfft(data[side], full) * np.fft.rfft(ir, full), full)
        out[side] = conv * wet * 2
        out[side, :data.shape[1]] += data[side] * (1 - wet)
    return out


# --- loudness (ITU-R BS.1770) ---------------------------------------------------------

def _biquad(b, a, w):
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def k_weight(data, rate=RATE):
    """BS.1770's K-weighting (a +4 dB high shelf and a 38 Hz high-pass) at any rate."""
    size = data.shape[1]
    w = 2 * np.pi * np.fft.rfftfreq(size, 1 / rate) / rate
    g, f0, q = 3.99984385397, 1681.97445095, 0.7071752369554193
    k = np.tan(np.pi * f0 / rate)
    vh = 10 ** (g / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    h = _biquad(((vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0,
                 (vh - vb * k / q + k * k) / a0),
                (1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0), w)
    f0, q = 38.13547087613982, 0.5003270373253953
    k = np.tan(np.pi * f0 / rate)
    a0 = 1 + k / q + k * k
    h *= _biquad((1.0, -2.0, 1.0), (1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0), w)
    return np.fft.irfft(np.fft.rfft(data, axis=1) * h, size, axis=1)


def momentary_max(data):
    """LUFS of the loudest 400 ms."""
    power = np.sum(k_weight(data) ** 2, axis=0)
    window = int(0.4 * RATE)
    power = np.pad(power, (0, max(0, window - len(power))))
    sums = np.concatenate(([0.0], np.cumsum(power)))
    return -0.691 + 10 * np.log10(((sums[window:] - sums[:-window]) / window).max())


def integrated(data):
    """Integrated LUFS: 400 ms blocks, 75 % overlap, the absolute and relative gates."""
    power = np.sum(k_weight(data) ** 2, axis=0)
    size, hop = int(0.4 * RATE), int(0.1 * RATE)
    sums = np.concatenate(([0.0], np.cumsum(power)))
    ends = sums[size::hop]
    z = (ends - sums[:-size:hop][:len(ends)]) / size
    z = z[-0.691 + 10 * np.log10(z + 1e-20) > -70]
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return -0.691 + 10 * np.log10(z.mean())


def balance_db(data):
    """Left minus right, in dB of K-weighted energy."""
    e = np.mean(k_weight(data) ** 2, axis=1)
    return 10 * np.log10((e[0] + 1e-20) / (e[1] + 1e-20))


def centre(data):
    """The same K-weighted energy on both sides. The room is random noise, so one side
    can ring a few dB louder at a pitch; this evens the whole file and still keeps
    a travelling sound's journey."""
    e = np.mean(k_weight(data) ** 2, axis=1)
    return data * np.sqrt(e.mean() / e)[:, None]


def ceiling(data):
    top = np.abs(data).max()
    return data * (PEAK / top) if top > PEAK else data


# --- finishing ------------------------------------------------------------------------

def done(tr, wet=0.3, room=1.8):
    """An effect: the room, the silent tail cut, soft ends (a few ms of silence, a
    raised-cosine fade-in, a smooth fade-out), even left and right, -16 LUFS
    momentary max, never above -3 dBFS."""
    data = reverb(tr.data, wet, room)
    env = np.abs(data).max(axis=0)
    loud = np.nonzero(env > env.max() * 0.01)[0]
    data = data[:, :loud[-1] + 1] if len(loud) else data
    fade = min(int(0.3 * RATE), data.shape[1] // 3)
    data[:, -fade:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fade))) ** 1.5
    m = int(0.004 * RATE)
    data[:, :m] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, m))
    data = np.concatenate((np.zeros((2, int(0.006 * RATE))), data), axis=1)
    data = centre(data)
    data *= 10 ** ((EFFECT_LUFS - momentary_max(data)) / 20)
    return ceiling(data)


def loop_done(tr, seconds, wet=0.42, room=3.0):
    """A music loop: the room on everything, then whatever rings past the end folded
    back onto the start, so it wraps round with no seam. Even left and right, -24
    LUFS integrated, under -3 dBFS. Plain gains only, which keep the seam."""
    data = reverb(tr.data, wet, room)
    size = int(seconds * RATE)
    out = np.zeros((2, size))
    for start in range(0, data.shape[1], size):
        part = data[:, start:start + size]
        out[:, :part.shape[1]] += part
    out = centre(out)
    out *= 10 ** ((LOOP_LUFS - integrated(out)) / 20)
    return ceiling(out)


def write_wav(path, data):
    """16-bit stereo PCM .wav at 32 kHz."""
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2").T.copy()
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def report(name, data, loop=False):
    """One line to check a sound against the rules."""
    peak = 20 * np.log10(np.abs(data).max())
    loud = integrated(data) if loop else momentary_max(data)
    kind = "integrated" if loop else "momentary max"
    print(f"{name}: {data.shape[1] / RATE:.2f} s, {loud:.1f} LUFS {kind}, "
          f"peak {peak:.1f} dBFS, L-R {balance_db(data):+.2f} dB")
