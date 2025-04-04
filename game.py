import requests
import json
import re
import os
import textwrap
import argparse
from colorama import Fore, Style, init
import traceback
import sys
import time
import copy
import pygame

# Optional Gemini imports - will be imported only if needed
gemini_available = False
try:
    from google import genai
    from google.genai import types

    gemini_available = True
except ImportError:
    pass

# Initialize colorama for cross-platform colored terminal output
init()

# Parse command line arguments
parser = argparse.ArgumentParser(description="Local Adventure Game")
parser.add_argument(
    "--debug", "-d", action="store_true", help="Enable debug mode"
)
parser.add_argument(
    "--api",
    type=str,
    default="http://192.168.1.74:1234/v1",
    help="LM Studio API base URL",
)
parser.add_argument(
    "--model",
    type=str,
    default="local",
    choices=["local", "gemini"],
    help="Model to use: local or gemini",
)
parser.add_argument(
    "--gemini-model",
    type=str,
    default="gemini-2.0-flash",
    help="Gemini model to use (if --model=gemini)",
)
parser.add_argument(
    "--temperature", type=float, default=0.7, help="Temperature for generation"
)
parser.add_argument(
    "--restore",
    type=str,
    help="Path to a saved game state file to restore from.",
)
args = parser.parse_args()

# LM Studio API endpoint
API_URL = f"{args.api}/chat/completions"

# Debug flag - can be set via command line or toggled in-game
DEBUG = args.debug

# Initialize Gemini client if selected
gemini_client = None
if args.model == "gemini":
    if not gemini_available:
        print("Error: Gemini API selected but required packages are not installed.")
        print("Please install with: pip install google-genai")
        exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        exit(1)

    gemini_client = genai.Client(api_key=api_key)

def setup_controller():
    """Initialize pygame and controller support."""
    pygame.init()
    pygame.joystick.init()
    
    # Check if any controllers are connected
    controller_count = pygame.joystick.get_count()
    if controller_count == 0:
        print_wrapped("No controllers detected. Using keyboard controls.", Fore.YELLOW)
        return None
    
    # Initialize the first controller
    controller = pygame.joystick.Joystick(0)
    controller.init()
    print_wrapped(f"Controller connected: {controller.get_name()}", Fore.GREEN)
    return controller

def get_selected_action(controller, possible_actions):
    """Get the currently selected action based on analog stick position."""
    if not controller or not possible_actions:
        return None
    
    # Get the left analog stick position
    x_axis = controller.get_axis(0)
    y_axis = controller.get_axis(1)
    
    # Determine which quadrant the stick is pointing to
    if len(possible_actions) <= 1:
        return 0  # Only one option
    elif len(possible_actions) == 2:
        # For two options, use left/right
        if x_axis < -0.25:
            return 0
        elif x_axis > 0.25:
            return 1
        else:
            return None
    else:
        # For 3-4 options, use quadrants
        if x_axis < -0.25 and y_axis < -0.25:  # Top-left
            return 0
        elif x_axis > 0.25 and y_axis < -0.25:  # Top-right
            return 1
        elif x_axis < -0.25 and y_axis > 0.25:  # Bottom-left
            return 2
        elif x_axis > 0.25 and y_axis > 0.25 and len(possible_actions) > 3:  # Bottom-right
            return 3
        else:
            return None

selected_index = 0

def handle_controller_input(controller, game_state):
    """Process controller input and return the player's action."""
    if not controller:
        return None
    
    # Process pygame events to update controller state
    pygame.event.pump()
    
    possible_actions = game_state.get("playerCharacter", {}).get("possibleActions", [])
    possible_selected_index = get_selected_action(controller, possible_actions)

    global selected_index
    # Highlight the currently selected action if any
    if possible_selected_index is not None:
        selected_index = possible_selected_index
        clear_screen()
        print_wrapped("\nPossible actions:", Fore.CYAN)
        for i, action in enumerate(possible_actions):
            if i == selected_index:
                print_wrapped(f"{i+1}. {action} <<<", Fore.GREEN)
                # Read the selected option with TTS
                speak(action)
            else:
                print_wrapped(f"{i+1}. {action}", Fore.WHITE)
        return None
    
    # Check button presses
    if controller.get_button(0):  # A button
        if selected_index is not None and selected_index < len(possible_actions):
            return possible_actions[selected_index]
        return None
    elif controller.get_button(1):  # B button
        return "try something else"
    elif controller.get_button(2):  # X button
        return "look around"
    elif controller.get_button(3):  # Y button
        return "check inventory"
    elif controller.get_button(7):  # Start/Menu button
        return "what is my objective"
    elif controller.get_axis(5) > 0.5:  # Right trigger
        return "attack"
    elif controller.get_axis(4) > 0.5:  # Left trigger
        return "defend"
    
    return None

def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_wrapped(text, color=None):
    """Print text with word wrapping and optional color."""
    wrapped_text = textwrap.fill(text, width=80)
    if color:
        print(f"{color}{wrapped_text}{Style.RESET_ALL}")
    else:
        print(wrapped_text)


def print_debug(title, content, color=Fore.MAGENTA):
    """Print debug information with formatting."""
    if DEBUG:
        print("\n" + "=" * 80)
        print_wrapped(f"{color}[DEBUG] {title}{Style.RESET_ALL}", color)
        print("-" * 80)

        # Format content based on type
        if isinstance(content, dict) or isinstance(content, list):
            formatted_content = json.dumps(content, indent=2)
            print(formatted_content)
        else:
            print(content)

        print("=" * 80 + "\n")


def call_gemini(prompt, temperature=0.7, max_tokens=8192):
    """Call the Gemini API with the given prompt."""
    try:

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=0.95,
            top_k=40,
            max_output_tokens=max_tokens,
            response_mime_type="text/plain",
        )

        response = gemini_client.models.generate_content(
            model=args.gemini_model,
            contents=contents,
            config=generate_content_config,
        )

        result = response.text

        return result
    except Exception as e:
        print_debug("Gemini API Error", str(e), Fore.RED)
        print_wrapped(f"Error calling Gemini API: {e}", Fore.RED)
        return None


def call_local_llm(messages, temperature=0.7, max_tokens=1024):
    """Call the LM Studio API with the given messages."""
    try:
        if DEBUG:
            print_debug(
                "LM Studio API Request",
                {"temperature": temperature, "messages": messages},
            )

        response = requests.post(
            API_URL,
            json={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]

        if DEBUG:
            print_debug("LM Studio API Response", result, Fore.GREEN)

        return result
    except requests.exceptions.RequestException as e:
        print_debug("LM Studio API Error", str(e), Fore.RED)
        print_wrapped(f"Error calling LM Studio API: {e}", Fore.RED)
        return None


def call_llm(messages, temperature=None, max_tokens=None):
    """Call the selected LLM API with the given messages."""
    # Use provided temperature or default from args
    temp = temperature if temperature is not None else args.temperature

    if args.model == "gemini":
        # For Gemini, convert the messages to a single prompt
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
            else:
                prompt += f"{role}: {content}\n\n"

        # Default max tokens for Gemini
        tokens = max_tokens if max_tokens is not None else 8192
        response = call_gemini(prompt, temperature=temp, max_tokens=tokens)
        if response is None:
            print_wrapped(
                "Gemini API failed, falling back to local model.", Fore.RED
            )
            args.model = "local"  # Switch to local model
            return call_local_llm(
                messages, temperature=temp, max_tokens=tokens
            )  # Call local model
        return response
    else:
        # Default max tokens for local LLM
        tokens = max_tokens if max_tokens is not None else 1024
        return call_local_llm(messages, temperature=temp, max_tokens=tokens)


# Game state specification - centralized for reuse
STATE_SPEC = """
The game state should be in JSON format with the following structure:

{
  "gameStatus": "playing", // Can be "playing", "win", or "lose"
  "date": "current-date",
  "time": "current-time",
  "objective": "Description of the win objective",
  "playerCharacter": {
    "name": "player-name",
    "beingType": "human/animal/etc",
    "location": "current-location-name",
    "inventory": [
      {
        "name": "item-name",
        "description": "brief description"
      }
    ],
    "statusEffects": [
      {
        "description": "Brief description of status",
        "startTime": "When the status was first aquired",
        "expired": false
      }
    ]
    "possibleActions": [
        "2/4 word description of each interesting and unique action"
    ]
  },
  "characters": [
    {
      "name": "character-name",
      "beingType": "human/animal/etc",
      "emotion": "current-emotion",
      "location": "current-location-name",
      "description": "brief description",
      "thoughts": "what the character is thinking",
      "inventory": [
        {
          "name": "item-name",
          "description": "brief description"
        }
      ],
      "statusEffects": []
    }
  ],
  "locations": [
    {
      "name": "location-name",
      "explored": true/false,
      "description": "brief description",
      "adjacentLocations": {
        "cardinal-direction-or-other-preposition": "adjacent-location-name"
      }
    }
  ]
}
"""

def generate_scenario():
    """Generate the initial game scenario with a win objective."""
    scenario_prompt = """
    As the narrator of this text adventure game, describe what happens next.

    Create an interesting starting scenario with the following:
    0. What is the date and time
    1. Who/what the player is (could be a normal person, a wizard, a talking animal, etc.)
    2. Where they are starting their adventure
    3. What items they have in their inventory (2-4 items)
    4. A brief description of the surroundings and situation, and what other characters are at this location
    5. A clear win objective for the player to achieve (find an item, reach a location, solve a puzzle, etc.)
    
    Keep your response to at most 1 short paragraph, and use simple language that someone learning english would understand.
    The story should be somewhat fantastical but grounded, like a simple but wise fable.
    Don't be too verbose, just a short paragraph. Use words a 4 year old would understand.
    There should be a cat named flowers in the story.
    Clearly state the win objective at the end.
    """

    messages = [{"role": "user", "content": scenario_prompt}]
    scenario = call_llm(messages, temperature=0.9)
    return scenario


def initialize_game_state(scenario):
    """Initialize the JSON game state based on the scenario."""
    # Create base JSON structure
    base_state = {
        "gameStatus": "playing",
        "objective": "Not yet determined",
        "playerCharacter": {
            "beingType": "none",
            "location": "none",
            "inventory": [],
            "statusEffects": [],
        },
        "characters": [],
        "locations": [],
    }

    # Extract information from scenario using the state aggregator
    state_prompt = f"""
    Based on this initial scenario description:
    
    "{scenario}"
    
    Update this JSON game state to reflect:
    1. The win objective
    2. The character type and starting location
    3. Inventory items
    4. The starting location details (description, characters, adjacent locations, any special access rules)
    
    Here's the template:
    
    {json.dumps(base_state, indent=2)}
    
    {STATE_SPEC}
    
    Return ONLY the updated JSON, nothing else.
    """

    messages = [{"role": "user", "content": state_prompt}]
    json_response = call_llm(messages, temperature=0.2)

    # Extract JSON from response
    try:
        # Try to find a JSON object in the response
        json_match = re.search(r"({[\s\S]*})", json_response)
        if json_match:
            json_str = json_match.group(1)
            game_state = json.loads(json_str)
            if DEBUG:
                print_debug("Initial Game State", game_state, Fore.BLUE)
            return game_state
        else:
            # If no JSON found, try to parse the entire response
            game_state = json.loads(json_response)
            if DEBUG:
                print_debug("Initial Game State", game_state, Fore.BLUE)
            return game_state
    except json.JSONDecodeError as e:
        # Fallback if JSON extraction fails
        print_debug(
            "JSON Extraction Failed",
            f"Error: {str(e)}\nResponse: {json_response}",
            Fore.RED,
        )
        return base_state


def update_game_state(current_state, player_request, narrator_response):
    """Update the game state based on the narrator's response."""
    state_prompt = f"""
    Given the current game state:
    
    {json.dumps(current_state, indent=2)}

    And the player's requested action:

    {player_request}
    
    And the narrator's latest response:
    
    "{narrator_response}"
    
    Update the JSON game state to reflect any changes that occurred in the narrator's response, you can consider the player's requested action as well
    but only if the narrator has allowed for it:

    -1. PLAYER ACTIONS:
        - Every time, you must come up with some new possible actions for the character to perform, these actions must be interesting and move the plot forward
        - Please maintain the list of possible player actions to 4 at most, keeping the most pertenant ones, and discarding the rest
        - Remember that the player can:
            - Move around between adjacent locations, using either a preposition or cardinal direction
            - Talk to people and animals
            - Use items from their inventory
            - Interact with the environment

    0. TIME CHANGES:
       - Track any changes to the time or date from the narration
       - Time must always pass, however slight, even in seconds is fine, but it must be a later time than before
    
    1. LOCATION CHANGES:
       - If the player moved to a new location, update the current location, mark that location as explored
       - If a new location was discovered, add it to the locations list
       - Update adjacent locations if new paths were discovered
       - If a character is at this location, add it to the characters list
    
    2. INVENTORY CHANGES:
       - Add items that were picked up
       - Remove items that were used or lost
    
    3. STATUS CHANGES: 
       - Add or remove status effects based on what happened, this could be the stance of the player, the condition of their body or clothes,
       or their involuntary emotions or gut reactions, any meaningful knowledge is also considered a status
       - An added status must have the current time and date attached to it
       - If a status effect was expired already, you can remove it
       - If it's been long enough, set the status effect as expired, if this is reasonable

    4. CHARACTER CHANGES:
        - If the player interacts with a character, update that character's thoughts, inventory, and statusEffects
        - If the character moves somewhere else, update their location, and create or update the location they enter if necessary
    
    4. WIN/LOSE CONDITIONS:
       - Check if the player has achieved the objective. If so, set gameStatus="win"
       - If the player died or became permanently trapped, set gameStatus="lose"

    If the narrator provides additional information to anything, feel free to update the existing JSON data where appropriate!
    
    {STATE_SPEC}
    
    Return ONLY the updated JSON, nothing else.
    """

    messages = [{"role": "user", "content": state_prompt}]
    json_response = call_llm(messages, temperature=0.2)

    # Extract JSON from response
    try:
        # Try to find a JSON object in the response
        if json_response is None:
            print_wrapped(
                "LLM returned None, using previous game state.", Fore.RED
            )
            return current_state

        json_match = re.search(r"({[\s\S]*})", json_response)
        if json_match:
            json_str = json_match.group(1)
            updated_state = json.loads(json_str)
            if DEBUG:
                print_debug("Updated Game State", updated_state, Fore.BLUE)
            return updated_state
        else:
            # If no JSON found, try to parse the entire response
            updated_state = json.loads(json_response)
            if DEBUG:
                print_debug("Updated Game State", updated_state, Fore.BLUE)
            return updated_state
    except json.JSONDecodeError as e:
        # Fallback if JSON extraction fails
        print_debug(
            "JSON Extraction Failed",
            f"Error: {str(e)}\nResponse: {json_response}",
            Fore.RED,
        )
        return current_state


def get_narrator_response(current_state, player_action, last_response=None):
    """Get the narrator's response to the player's action."""
    # Check game status
    game_status = current_state.get("gameStatus", "playing")

    # If game is over, limit the narrator's response
    if game_status in ["win", "lose"]:
        return (
            "The game is over. You have {game_status}! Type 'quit' to exit or"
            " 'restart' to play again."
        ).format(game_status=game_status)

    context = ""
    if last_response:
        context = f'Your last narration was: "{last_response}"\n\n'

    # Create a clean version of the game state without possible actions
    clean_state = copy.deepcopy(current_state)
    if "playerCharacter" in clean_state and "possibleActions" in clean_state["playerCharacter"]:
        del clean_state["playerCharacter"]["possibleActions"]

    narrator_prompt = f"""
    {context}The current game state is:
    
    {json.dumps(clean_state, indent=2)}
    
    The player's action is: "{player_action}"
    
    As the narrator of this text adventure game, describe what happens next.
    
    If the player tries to do something impossible, gently explain why it can't be done.
    If the player achieves their objective, make it clear they've won the game!
    If the player does something that would result in death or being permanently trapped, describe it dramatically.
    Make the player aware of any passage of time.
    Describe locations by relative cardinal directions or prepositions from current location.

    Please keep your response to 1 or 2 sentences. Use simple common american english, and avoid poetic phrasing and unnecessary fluff.
    """

    messages = [{"role": "user", "content": narrator_prompt}]
    return call_llm(messages, temperature=0.8)


def check_game_over(game_state):
    """Check if the game is over and return appropriate message."""
    try:
        game_status = game_state.get("gameStatus", "playing")
        objective = game_state.get("objective", "Unknown objective")

        if game_status == "win":
            return (
                True,
                "CONGRATULATIONS! You've won the game!\nObjective completed:"
                f" {objective}",
            )
        elif game_status == "lose":
            return (
                True,
                "GAME OVER! You've lost the game.\nUnfulfilled objective:"
                f" {objective}",
            )
        else:
            return False, ""
    except:
        return False, ""


def toggle_debug():
    """Toggle the debug mode."""
    global DEBUG
    DEBUG = not DEBUG
    status = "ON" if DEBUG else "OFF"
    print_wrapped(f"\nDebug mode: {status}", Fore.MAGENTA)
    return f"Debug mode toggled {status}"


def save_game_state(game_state, filename="game_state.json"):
    """Saves the game state to a JSON file."""
    try:
        with open(filename, "w") as f:
            json.dump(game_state, f, indent=2)
        print_wrapped(f"Game state saved to {filename}", Fore.GREEN)
    except Exception as e:
        print_wrapped(f"Error saving game state: {e}", Fore.RED)


def load_game_state(filename="game_state.json"):
    """Loads the game state from a JSON file."""
    try:
        with open(filename, "r") as f:
            game_state = json.load(f)
        print_wrapped(f"Game state loaded from {filename}", Fore.GREEN)
        return game_state
    except FileNotFoundError:
        print_wrapped(
            "No saved game state found. Starting a new game.", Fore.YELLOW
        )
        return None
    except Exception as e:
        print_wrapped(f"Error loading game state: {e}", Fore.RED)
        return None

import subprocess
import shutil

# Add these global variables
speak_process = None
audio_process = None
stop_speaking = False

def stop_speaking_handler():
    """Stop the TTS and audio playback"""
    global speak_process, audio_process, stop_speaking
    stop_speaking = True
    
    if speak_process and speak_process.poll() is None:
        speak_process.terminate()
    if audio_process and audio_process.poll() is None:
        audio_process.terminate()

def speak_in_background(text):
    """Speak text using Piper in the background"""
    global speak_process, audio_process, stop_speaking
    stop_speaking = False
    
    piper_path = "./piper/piper"
    if not os.path.exists(piper_path):
        print_wrapped("Piper not found! Please check the installation.", Fore.RED)
        return

    if not shutil.which("aplay"):
        print_wrapped("ALSA utilities (aplay) not found!", Fore.RED)
        return

    model_path = "./piper/models/en_GB-alan-low.onnx"

    piper_process = subprocess.Popen(
        [piper_path, "--output_raw", "--model", model_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    audio_process = subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", "24000", "-c", "1"],
        stdin=piper_process.stdout
    )

    speak_process = piper_process
    audio_process = audio_process

def speak(text):
    """Speak text with interruptible playback"""
    global stop_speaking
    stop_speaking = False
    
    # Start speaking in background
    speak_thread = threading.Thread(target=speak_in_background, args=(text,))
    speak_thread.daemon = True
    speak_thread.start()

    # Monitor for stop request
    while speak_thread.is_alive() and not stop_speaking:
        if os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode()
                if key.lower() == 's':
                    stop_speaking_handler()
                    break
        else:
            import select
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if rlist:
                key = sys.stdin.read(1).lower()
                if key == 's':
                    stop_speaking_handler()
                    break
        time.sleep(0.1)

    # Wait for processes to terminate
    while speak_process and speak_process.poll() is None:
        time.sleep(0.1)
    while audio_process and audio_process.poll() is None:
        time.sleep(0.1)

def main():
    clear_screen()
    welcome_message = "Welcome to Local Adventure!"
    speak(welcome_message)
    print_wrapped(welcome_message, Fore.CYAN)
    print_wrapped("Type 'quit' at any time to exit the game.", Fore.YELLOW)
    print_wrapped("Type 'debug' to toggle debug information.", Fore.YELLOW)
    print_wrapped("Type 'restart' to start a new game.", Fore.YELLOW)

    if DEBUG:
        print_wrapped(
            "Debug mode is enabled. Type 'debug' to disable it.", Fore.MAGENTA
        )
        if args.model == "gemini":
            print_wrapped(
                f"Using Gemini API with model: {args.gemini_model}",
                Fore.MAGENTA,
            )
        else:
            print_wrapped(
                f"Using LM Studio API endpoint: {API_URL}", Fore.MAGENTA
            )

    # Initialize controller
    controller = setup_controller()
    if controller:
        print_wrapped("Xbox controller connected. Use analog stick to select actions.", Fore.GREEN)
        print_wrapped("A: Confirm selection, B: Try something else", Fore.GREEN)
        print_wrapped("X: Look around, Y: Check inventory", Fore.GREEN)
        print_wrapped("Start: Check objective, RT: Attack, LT: Defend", Fore.GREEN)

    def start_game():
        print_wrapped("\nGenerating your adventure...", Fore.GREEN)

        scenario = generate_scenario()
        game_state = initialize_game_state(scenario)

        print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)
        print_wrapped(scenario, Fore.WHITE)
        print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)

        speak(scenario)

        return scenario, game_state

    # Initialize the game
    if args.restore:
        game_state = load_game_state(args.restore)
        if game_state:
            last_response = "Game restored from saved state."
        else:
            last_response, game_state = start_game()
    else:
        game_state = load_game_state()
        if game_state:
            last_response = "Game restored from saved state."
        else:
            last_response, game_state = start_game()

    while True:
        # Check if game is over
        game_over, message = check_game_over(game_state)
        if game_over:
            print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)
            if "won" in message:
                print_wrapped(message, Fore.GREEN)
            else:
                print_wrapped(message, Fore.RED)
            print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)
            print_wrapped(
                "Type 'restart' to play again or 'quit' to exit.", Fore.YELLOW
            )

        # Display possible actions
        possible_actions = game_state.get("playerCharacter", {}).get("possibleActions", [])
        if possible_actions:
            print_wrapped("\nPossible actions:", Fore.CYAN)
            for i, action in enumerate(possible_actions, start=1):
                print_wrapped(f"{i}. {action}", Fore.WHITE)

        # Get player action - either from controller or keyboard
        player_action = None
        
        if controller:
            # Controller input loop
            print_wrapped("\nUse controller to select an action, or type to enter manually", Fore.YELLOW)
            while not player_action:
                # Check for keyboard input
                if os.name == 'nt':
                    import msvcrt
                    if msvcrt.kbhit():
                        # Switch to keyboard input
                        player_action = input("> ")
                        break
                else:
                    import select
                    if select.select([sys.stdin], [], [], 0)[0]:
                        # Switch to keyboard input
                        player_action = input("> ")
                        break
                
                # Check controller input
                controller_action = handle_controller_input(controller, game_state)
                if controller_action:
                    player_action = controller_action
                    print_wrapped(f"> {player_action}", Fore.GREEN)
                    break
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
        else:
            # Keyboard-only input
            print_wrapped("\nWhat would you like to do?", Fore.YELLOW)
            player_action = input("> ")

        if player_action.lower() in ["quit", "exit", "q"]:
            print_wrapped("\nThanks for playing!", Fore.CYAN)
            break
        elif player_action.lower() == "debug":
            message = toggle_debug()
            print_wrapped(message, Fore.MAGENTA)
            continue
        elif player_action.lower() == "restart":
            print_wrapped("\nRestarting the game...", Fore.GREEN)
            last_response, game_state = start_game()
            continue

        print_wrapped("\nThinking...", Fore.GREEN)
        narrator_response = get_narrator_response(
            game_state, player_action, last_response
        )

        print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)
        print_wrapped(narrator_response, Fore.WHITE)
        print_wrapped("\n" + "=" * 80 + "\n", Fore.CYAN)

        speak(narrator_response)

        game_state = update_game_state(
            game_state, player_action, narrator_response
        )

        last_response = narrator_response
        save_game_state(game_state)

    # Clean up pygame when exiting
    if controller:
        pygame.quit()

if __name__ == "__main__":
    main()
