# Model Card for the AI Game Master (Game Glitch Investigator)

**System:** an agentic hint generator for a Streamlit number guessing game. On
each guess, Claude (`claude-opus-5`) writes a hint styled to the chosen
difficulty, a second model call checks whether that hint gives away the secret
or points the wrong way, and the loop either regenerates a better hint or falls
back to the plain built in one. You can read the full architecture in
`README.md` and the reliability results in `EVALUATION.md`.

Everything below is written in my own words, and all of it is based on things
that actually came up while I was building and testing the project.

## Limitations and Biases

The checker that grades each hint is itself a language model, so it is a good
safety net but not a guarantee. It reliably catches a hint that prints the
actual digits of the secret, but a sneakier leak could still get through, like
spelling the number out as "fifty" or dropping a clue like "half of one
hundred." My separate reliability harness only looks for the digits, so word
based or math based leaks are a blind spot I know about.

The hints are also not predictable. The same guess can produce different wording
every time, which means I can never promise an exact experience or test the
exact text. All I can really test is the safety logic wrapped around the model.

There is a real cost to this design too. Every hint takes two API calls instead
of an instant string, so it is slower and it costs money, and that is the trade
I made to get verification.

Finally there is bias baked into the tone. The hints are in English and lean on
idioms and a game show or riddle persona that might not translate well or might
confuse someone who does not speak English as a first language. The idea that
"Hard" should mean "cryptic" is my own subjective call, not a universal one. And
on a small range like 1 to 20, even a careful hint narrows things down fast, so
"do not reveal the number" protects the player less than it does on 1 to 100.

## Could the AI Be Misused, and How Would I Prevent That?

The most realistic risk is prompt injection through the guess history. The
game keeps track of what the player typed, including invalid entries that are
just free text, and that history gets handed to the hint prompt. A player could
type instructions instead of a number to try to trick the Game Master into
revealing the secret or breaking character. The fix is to clean the history
before sending it, passing only the real numeric guesses and dropping any free
text, and to lean on the self check as a second line of defense if something
does slip through.

There is also the ordinary risk of someone abusing the API key to run up
charges. I keep the key in a `.env` file that is never committed and never
logged, and the account rate limits cap how much damage a leaked key could do.

More broadly, the write and check pattern is generic, so in theory it could be
pointed at harmful content if the prompts were swapped out. In this project the
prompts are narrow and only ever ask for game hints, and the checker plus the
built in fallback keep a tight lid on what actually reaches the player.

On privacy, the log only records game data such as guesses, the secret, and the
checker's verdicts. There is no personal information in it, but I still kept it
local and out of version control instead of sending it anywhere.

## What Surprised Me While Testing Reliability

The thing that caught me off guard is that my own code around the model needed
testing far more than the model did. The worst reliability bugs I hit were not
in Claude's hints at all. They were in my test file and my evaluation script, a
leftover import that did not exist and a crash from printing emoji on a Windows
console. It turned out that "testing the AI" mostly meant hardening everything
that surrounds it.

I also learned that mocking the model lets me prove the loop is reliable, that
it rejects leaks and always falls back, without ever checking the wording of a
hint. At first that felt like cheating, but it is actually the right thing to
test, because the wording changes every time and the safety behavior should not.

The last surprise was that running with no API key ended up being a passing
state instead of a failure. I expected missing credentials to break things, but
the fallback turned it into a clean run with zero leaks. Designing for graceful
failure quietly turned an error into a feature.

## Collaboration with AI During This Project

I worked with Claude the way I would work with a coding partner. I let it help me
design and write the Game Master, but I checked its work by running the tests and
the app instead of just trusting what it handed me.

One suggestion that really helped came when I described my worry that an AI hint
could accidentally give away the answer. Claude suggested the write, check, and
fix loop with a built in fallback, and it specifically said to ground the checker
in the game's existing `check_guess` logic rather than letting the AI judge the
direction on its own. That was a genuinely good call. It changed the design from
"hope the hint is safe" to "check it against the real rules, and fall back if it
is not." I confirmed it worked by writing tests that feed the loop a hint that
leaks the answer and watching it get rejected.

One suggestion that was wrong came while it was writing my test file. Claude
added a line that imported a module that does not exist. If I had pasted the code
in without looking, the whole test suite would have failed to even load and would
have run zero tests. I caught it by running pytest, saw the import error, and
deleted the line. It was the exact same lesson from the original debugging lab
coming back around: AI code should be doubted and run before it is trusted, no
matter how confident it looks.
