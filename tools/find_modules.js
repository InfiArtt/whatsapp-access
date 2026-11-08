// Module names matching each pattern, for tools/probe.py -f. Edit PATTERNS to search.
	const PATTERNS = (globalThis.__probePatterns || "").split("|").filter(Boolean);
	const names = Object.keys(window.require("__debug").modulesMap);
	const out = {};
	for (const p of PATTERNS) {
		const re = new RegExp(p, "i");
		out[p] = names.filter((n) => re.test(n)).slice(0, 60);
	}
	return out;
