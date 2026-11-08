// For tools/source.sh: a module's definition, found in WhatsApp's own script files (fetched from the cache).
const name = globalThis.__module;
const max = globalThis.__max || 6000;
if (!globalThis.__waScripts) {
	const urls = [...new Set(performance.getEntriesByType("resource").map((e) => e.name).filter((u) => /\.js(\?|$)/.test(u)))];
	urls.push(...[...document.scripts].map((s) => s.src).filter(Boolean));
	globalThis.__waScripts = {};
	for (const url of [...new Set(urls)]) {
		try {
			globalThis.__waScripts[url] = await (await fetch(url)).text();
		} catch (e) {}
	}
}
const marker = `__d("${name}"`;
for (const text of Object.values(globalThis.__waScripts)) {
	const at = text.indexOf(marker);
	if (at >= 0) {
		const end = text.indexOf('__d("', at + marker.length);
		return text.slice(at, Math.min(end < 0 ? text.length : end, at + max));
	}
}
return "not found in " + Object.keys(globalThis.__waScripts).length + " scripts";
