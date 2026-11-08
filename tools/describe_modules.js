// For tools/probe.py: the exports of the modules in NAMES, each with its arity and the start of its source.
	const NAMES = globalThis.__names || [];
	const out = {};
	for (const name of NAMES) {
		try {
			const m = window.require(name);
			const e = {};
			for (const k of Object.keys(m || {})) {
				const v = m[k];
				e[k] = typeof v === "function" ? `fn/${v.length}: ${String(v).slice(0, 220)}` : typeof v;
			}
			out[name] = e;
		} catch (err) {
			out[name] = "ERROR " + err.message;
		}
	}
	return out;
