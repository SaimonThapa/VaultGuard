// All randomness comes from crypto.getRandomValues, with unbiased selection (never `% length`
// on a raw random number).

// Uniform integer in [0, max) by rejection sampling.
export function randomInt(max) {
	const limit = Math.floor(0x100000000 / max) * max;
	const buf = new Uint32Array(1);
	do {
		crypto.getRandomValues(buf);
	} while (buf[0] >= limit);
	return buf[0] % max;
}

const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // 32 symbols = 5 bits each

// 128-bit key = 26 symbols (130 bits), 256-bit key = 52 symbols (260 bits), in groups of four.
export function crockfordKey(bits = 128) {
	const count = bits === 256 ? 52 : 26;
	const symbols = Array.from({ length: count }, () => CROCKFORD[randomInt(32)]);
	const groups = [];
	for (let i = 0; i < count; i += 4)
		groups.push(symbols.slice(i, i + 4).join(""));
	return groups.join("-");
}

const SETS = {
	upper: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
	lower: "abcdefghijklmnopqrstuvwxyz",
	digits: "0123456789",
	symbols: "!@#$%^&*()-_=+[]{};:,.?",
};

function shuffle(items) {
	for (let i = items.length - 1; i > 0; i--) {
		const j = randomInt(i + 1);
		[items[i], items[j]] = [items[j], items[i]];
	}
	return items;
}

// options: { length, upper, lower, digits, symbols }. Always includes one of each chosen set.
export function generatePassword({ length = 20, ...enabled }) {
	const chosen = Object.keys(SETS).filter((k) => enabled[k]);
	if (chosen.length === 0) throw new Error("Pick at least one character set");
	const pool = chosen.map((k) => SETS[k]).join("");
	const chars = chosen.map((k) => SETS[k][randomInt(SETS[k].length)]);
	while (chars.length < length) chars.push(pool[randomInt(pool.length)]);
	return shuffle(chars).join("");
}

// A scrambled-looking string for the lock animation (display only, not a secret).
export function noiseChar() {
	return "abcdefghijklmnopqrstuvwxyz0123456789+/="[randomInt(39)];
}
