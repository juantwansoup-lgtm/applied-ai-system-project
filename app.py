import random
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()  # pull ANTHROPIC_API_KEY from a local .env if present
except ImportError:
    pass

from logic_utils import check_guess, new_game_state
from game_master import generate_hint

def get_range_for_difficulty(difficulty: str):
    # Range grows with difficulty so higher levels are genuinely harder
    # (a bigger search space) and pair with fewer attempts below.
    if difficulty == "Easy":
        return 1, 20
    if difficulty == "Normal":
        return 1, 100
    if difficulty == "Hard":
        return 1, 200
    return 1, 100


def parse_guess(raw: str):
    if raw is None:
        return False, None, "Enter a guess."

    if raw == "":
        return False, None, "Enter a guess."

    try:
        if "." in raw:
            value = int(float(raw))
        else:
            value = int(raw)
    except Exception:
        return False, None, "That is not a number."

    return True, value, None


def update_score(current_score: int, outcome: str, attempt_number: int):
    if outcome == "Win":
        points = 100 - 10 * (attempt_number + 1)
        if points < 10:
            points = 10
        return current_score + points

    if outcome == "Too High":
        if attempt_number % 2 == 0:
            return current_score + 5
        return current_score - 5

    if outcome == "Too Low":
        return current_score - 5

    return current_score

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("An AI-generated guessing game. Something is off.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit_map = {
    "Easy": 8,   # small range (1-20), generous attempts
    "Normal": 7, # medium range (1-100)
    "Hard": 6,   # large range (1-200), fewest attempts
}
attempt_limit = attempt_limit_map[difficulty]

low, high = get_range_for_difficulty(difficulty)

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")

if "secret" not in st.session_state:
    st.session_state.secret = random.randint(low, high)

if "attempts" not in st.session_state:
    st.session_state.attempts = 1

if "score" not in st.session_state:
    st.session_state.score = 0

if "status" not in st.session_state:
    st.session_state.status = "playing"

if "history" not in st.session_state:
    st.session_state.history = []

st.subheader("Make a guess")

st.info(
    f"Guess a number between {low} and {high}. "
    f"Attempts left: {attempt_limit - st.session_state.attempts}"
)

with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("History:", st.session_state.history)
    # AI Game Master status for the last hint (players don't see this).
    st.write("Last hint source:", st.session_state.get("last_hint_source", "—"))
    st.write("Last hint attempts:", st.session_state.get("last_hint_attempts", "—"))
    note = st.session_state.get("last_hint_note", "")
    if note:
        st.write("Last hint note:", note)

raw_guess = st.text_input(
    "Enter your guess:",
    key=f"guess_input_{difficulty}"
)

col1, col2, col3 = st.columns(3)
with col1:
    submit = st.button("Submit Guess 🚀")
with col2:
    new_game = st.button("New Game 🔁")
with col3:
    show_hint = st.checkbox("Show hint", value=True)

if new_game:                                #FIX: Refactored logic into logic_utils.py using agent mode
    st.session_state.update(new_game_state(random.randint(low, high)))
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    st.session_state.attempts += 1

    ok, guess_int, err = parse_guess(raw_guess)

    if not ok:
        st.session_state.history.append(raw_guess)
        st.error(err)
    else:
        st.session_state.history.append(guess_int)

        secret = st.session_state.secret

        outcome, message = check_guess(guess_int, secret)

        if show_hint:
            if outcome == "Win":
                st.warning(message)
            else:
                with st.spinner("The Game Master is thinking..."):
                    hint = generate_hint(
                        guess=guess_int,
                        secret=secret,
                        low=low,
                        high=high,
                        difficulty=difficulty,
                        history=st.session_state.history,
                    )
                # Record the AI status for the debug panel, then show a clean
                # hint to the player. Players never see the fallback note; it
                # lives in Developer Debug Info instead.
                st.session_state.last_hint_source = hint.source
                st.session_state.last_hint_attempts = hint.attempts
                st.session_state.last_hint_note = hint.note
                if hint.source == "ai":
                    st.warning(f"🔮 Game Master (AI): {hint.text}")
                    st.caption(f"AI hint verified in {hint.attempts} attempt(s).")
                else:
                    st.warning(hint.text)

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=st.session_state.attempts,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        else:
            if st.session_state.attempts >= attempt_limit:
                st.session_state.status = "lost"
                st.error(
                    f"Out of attempts! "
                    f"The secret was {st.session_state.secret}. "
                    f"Score: {st.session_state.score}"
                )

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
