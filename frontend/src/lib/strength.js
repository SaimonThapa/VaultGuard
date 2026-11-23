import { ZxcvbnFactory } from "@zxcvbn-ts/core";
import * as common from "@zxcvbn-ts/language-common";
import * as en from "@zxcvbn-ts/language-en";

// Instant feedback only: the backend re-checks every password (bypassable otherwise).
const zxcvbn = new ZxcvbnFactory({
	translations: en.translations,
	graphs: common.adjacencyGraphs,
	dictionary: { ...common.dictionary, ...en.dictionary },
});

const LABELS = ["Very weak", "Weak", "Okay", "Strong", "Very strong"];
export const MIN_SCORE = 3; // matches the backend rule

export function strengthOf(password, userInputs = []) {
	const result = zxcvbn.check(
		password.slice(0, 256),
		userInputs.filter(Boolean),
	);
	return {
		score: result.score,
		label: LABELS[result.score],
		guessesLog10: result.guessesLog10,
		hint: result.feedback.warning || result.feedback.suggestions[0] || "",
	};
}
