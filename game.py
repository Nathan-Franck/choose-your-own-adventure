import requests
import xml.etree.ElementTree as ET
import re
import os
import textwrap
import json
import argparse
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored terminal output
init()

# Parse command line arguments
parser = argparse.ArgumentParser(description='Local Adventure Game')
parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
parser.add_argument('--api', type=str, default="http://192.168.1.74:1234/v1", 
                    help='LM Studio API base URL')
args = parser.parse_args()

# LM Studio API endpoint
API_URL = f"{args.api}/chat/completions"

# Debug flag - can be set via command line or toggled in-game
DEBUG = args.debug

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

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
        print("\n" + "="*80)
        print_wrapped(f"{color}[DEBUG] {title}{Style.RESET_ALL}", color)
        print("-"*80)
        print(content)  # Don't wrap XML content - we'll format it specially
        print("="*80 + "\n")

def indent_xml(elem, level=0):
    """Custom XML indentation function for compatibility with all Python versions."""
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_xml(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def format_xml(xml_string):
    """Format XML string for better readability in the terminal."""
    try:
        # Parse the XML string
        root = ET.fromstring(xml_string)
        
        # Apply custom indentation
        indent_xml(root)
        
        # Convert to string with proper formatting
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Add proper XML declaration
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        # Format long attribute lines for better readability
        lines = xml_str.split('\n')
        result_lines = []
        
        for line in lines:
            # If line is too long and has multiple attributes, break it up
            if len(line) > 80 and ' ' in line and '=' in line:
                # Find tag opening and attributes
                tag_match = re.match(r'^(\s*)(<[^\s>]+)(.*?)(/?>)$', line)
                if tag_match:
                    indent, tag_open, attrs, tag_close = tag_match.groups()
                    
                    # Start with the opening tag
                    result_lines.append(f"{indent}{tag_open}")
                    
                    # Add each attribute on a new line with extra indentation
                    attr_indent = indent + "    "
                    attr_pairs = re.findall(r'\s+([^\s=]+)="([^"]*)"', attrs)
                    for name, value in attr_pairs:
                        result_lines.append(f"{attr_indent}{name}=\"{value}\"")
                    
                    # Add the closing bracket
                    result_lines.append(f"{indent}{tag_close}")
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    except Exception as e:
        print_debug("XML Formatting Error", str(e), Fore.RED)
        
        # Fallback formatting if the above fails
        try:
            # Basic indentation with minidom
            from xml.dom import minidom
            pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")
            # Remove extra blank lines
            pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
            return pretty_xml
        except:
            # Last resort: just return the original
            return xml_string

def call_llm(messages, temperature=0.7, max_tokens=1024):
    """Call the LM Studio API with the given messages."""
    try:
        # # Print debug info about the request
        # if DEBUG:
        #     debug_messages = json.dumps(messages, indent=2)
        #     print_debug("API Request", f"Temperature: {temperature}\nMessages:\n{debug_messages}")
        
        response = requests.post(
            API_URL,
            json={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]
        
        # # Print debug info about the response
        # if DEBUG:
        #     print_debug("API Response", result, Fore.GREEN)
            
        return result
    except requests.exceptions.RequestException as e:
        print_debug("API Error", str(e), Fore.RED)
        print_wrapped(f"Error calling LM Studio API: {e}", Fore.RED)
        return None
    
state_spec = """
    For the status effects section, use this format:
    <status-effect time="[time-since-first-applied]" expired="false/true">
        [Brief description of status]
    </status-effect>

    For the locations section, use this format:
    <location name="[location-name]" explored="false/true">
      <brief-description>[brief description]</brief-description>
      <adjacent-locations>
        <adjacent name="[adjacent-location-name]"/>
        <!-- More adjacent locations as needed -->
      </adjacent-locations>
    </location>

    For the characters section, use this format:
    <character name="[character-name]" being-type="[being-type]" emotion="[current-emotion]" location="[current-location]">
        <brief-description></brief-description>
        <thoughts>
        </thoughts>
        <inventory>
        </inventory>
        <status-effects>
        </status-effects>
    </character>
"""

def generate_scenario():
    """Generate the initial game scenario with a win objective."""
    scenario_prompt = """
    As the narrator of this text adventure game, describe what happens next.

    Create an interesting starting scenario with the following:
    1. Who/what the player is (could be a normal person, a wizard, a talking animal, etc.)
    2. Where they are starting their adventure
    3. What items they have in their inventory (2-4 items)
    4. A brief description of the surroundings and situation, and what other characters are at this location
    5. A clear win objective for the player to achieve (find an item, reach a location, solve a puzzle, etc.)
    
    Be creative, and engaging. Keep your response to at most 1 short paragraph, and use simple language that someone learning english would understand.
    We're not trying to be whimsical or goofy, but grounded, like a simple but wise fable.
    Don't be too verbose, just a short paragraph. Use words a 4 year old would understand.
    Clearly state the win objective at the end.
    """
    
    messages = [{"role": "user", "content": scenario_prompt}]
    scenario = call_llm(messages, temperature=0.9)
    return scenario

def initialize_game_state(scenario):
    """Initialize the XML game state based on the scenario."""
    # Create base XML structure with new elements
    base_xml = """
    <game-state game-status="playing">
      <objective>Not yet determined</objective>
      <player-character being-type="none" location="none">
        <inventory>
        </inventory>
        <status-effects>
        </status-effects>
      </player-character>
      <characters>
        <!-- Will be populated with discovered characters -->
      </characters>
      <locations>
        <!-- Will be populated with discovered locations -->
      </locations>
    </game-state>
    """
    
    # Extract information from scenario using the state aggregator
    state_prompt = f"""
    Based on this initial scenario description:
    
    "{scenario}"
    
    Update this XML game state to reflect:
    1. The win objective
    2. The character type and starting location
    3. Inventory items
    4. The starting location details (description, characters, adjacent locations, any special access rules)
    
    Here's the template:
    
    {base_xml}
    
    {state_spec}
    
    Return ONLY the updated XML, nothing else.
    """
    
    messages = [{"role": "user", "content": state_prompt}]
    xml_response = call_llm(messages, temperature=0.2)
    
    # Extract XML from response
    xml_match = re.search(r'<game-state.*?</game-state>', xml_response, re.DOTALL)
    if xml_match:
        xml_result = xml_match.group(0)
        if DEBUG:
            print_debug("Initial Game State", format_xml(xml_result), Fore.BLUE)
        return xml_result
    else:
        # Fallback if XML extraction fails
        print_debug("XML Extraction Failed", "Using base XML template", Fore.RED)
        return base_xml.strip()

def update_game_state(current_state, player_request, narrator_response):
    """Update the game state based on the narrator's response."""
    state_prompt = f"""
    Given the current game state:
    
    {current_state}

    And the player's requested action:

    {player_request}
    
    And the narrator's latest response:
    
    "{narrator_response}"
    
    Update the XML game state to reflect any changes that occurred in the narrator's response, you can consider the player's requested action as well
    but only if the narrator has allowed for it:
    
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
       or their involuntary emotions or gut reactions
       - If a status effect was expired already, you can remove it
       - If a status persists, add to its time attribute
       - If it's been long enough, set the status effect as expired, if this is reasonable

    4. CHARACTER CHANGES:
        - If the player interacts with a character, update that character's thoughts, inventory, and status-effects
        - If the character moves somewhere else, update their location, and create or update the location they enter if necessary
    
    4. WIN/LOSE CONDITIONS:
       - Check if the player has achieved the objective. If so, set game-status="win"
       - If the player died or became permanently trapped, set game-status="lose"

    If the narrator provides additional information to anything, feel free to update the existing xml data where appropriate!
    If the xml format is malformed, fix it, filling in any required missing information with "unknown"

    {state_spec}
    
    Return ONLY the updated XML, nothing else.
    """
    
    messages = [{"role": "user", "content": state_prompt}]
    xml_response = call_llm(messages, temperature=0.2)
    
    # Extract XML from response
    xml_match = re.search(r'<game-state.*?</game-state>', xml_response, re.DOTALL)
    if xml_match:
        xml_result = xml_match.group(0)
        if DEBUG:
            print_debug("Updated Game State", format_xml(xml_result), Fore.BLUE)
        return xml_result
    else:
        # Fallback if XML extraction fails
        print_debug("XML Extraction Failed", "Keeping previous state", Fore.RED)
        return current_state

def get_narrator_response(current_state, player_action, last_response=None):
    """Get the narrator's response to the player's action."""
    # Parse the XML to check game status
    try:
        root = ET.fromstring(current_state)
        game_status = root.find(".//game-state").get("game-status", "playing")
    except:
        game_status = "playing"
    
    # If game is over, limit the narrator's response
    if game_status in ["win", "lose"]:
        return f"The game is over. You have {game_status}! Type 'quit' to exit or 'restart' to play again."
    
    context = ""
    if last_response:
        context = f"Your last narration was: \"{last_response}\"\n\n"
    
    narrator_prompt = f"""
    {context}The current game state is:
    
    {current_state}
    
    The player's action is: "{player_action}"
    
    As the narrator of this text adventure game, describe what happens next.
    Be creative, and engaging. We're not trying to be whimsical or goofy, but grounded, like a simple but wise fable.
    
    Remember that the player can:
    - Move around between adjacent locations
    - Talk to people and animals
    - Use items from their inventory
    - Interact with the environment
    
    If the player tries to do something impossible, gently explain why it can't be done.
    If the player achieves their objective, make it clear they've won the game!
    If the player does something that would result in death or being permanently trapped, describe it dramatically.

    Please keep your response to 1 or 2 sentences. Use simple common american english.
    """
    
    messages = [{"role": "user", "content": narrator_prompt}]
    return call_llm(messages, temperature=0.8)

def check_game_over(game_state):
    """Check if the game is over and return appropriate message."""
    try:
        root = ET.fromstring(game_state)
        game_status = root.find(".//game-state").get("game-status", "playing")
        objective = root.find(".//objective").text
        
        if game_status == "win":
            return True, f"CONGRATULATIONS! You've won the game!\nObjective completed: {objective}"
        elif game_status == "lose":
            return True, f"GAME OVER! You've lost the game.\nUnfulfilled objective: {objective}"
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

def main():
    clear_screen()
    print_wrapped("Welcome to Local Adventure!", Fore.CYAN)
    print_wrapped("Type 'quit' at any time to exit the game.", Fore.YELLOW)
    print_wrapped("Type 'debug' to toggle debug information.", Fore.YELLOW)
    print_wrapped("Type 'restart' to start a new game.", Fore.YELLOW)
    
    if DEBUG:
        print_wrapped("Debug mode is enabled. Type 'debug' to disable it.", Fore.MAGENTA)
        print_wrapped(f"Using API endpoint: {API_URL}", Fore.MAGENTA)
    
    def start_game():
        print_wrapped("\nGenerating your adventure...", Fore.GREEN)
        
        scenario = generate_scenario()
        game_state = initialize_game_state(scenario)
        
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        print_wrapped(scenario, Fore.WHITE)
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        
        return scenario, game_state
    
    # Initialize the game
    last_response, game_state = start_game()
    
    while True:
        # Check if game is over
        game_over, message = check_game_over(game_state)
        if game_over:
            print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
            if "won" in message:
                print_wrapped(message, Fore.GREEN)
            else:
                print_wrapped(message, Fore.RED)
            print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
            print_wrapped("Type 'restart' to play again or 'quit' to exit.", Fore.YELLOW)
        
        print_wrapped("What would you like to do?", Fore.YELLOW)
        player_action = input("> ")
        
        if player_action.lower() in ['quit', 'exit', 'q']:
            print_wrapped("\nThanks for playing!", Fore.CYAN)
            break
        elif player_action.lower() == 'debug':
            message = toggle_debug()
            print_wrapped(message, Fore.MAGENTA)
            continue
        elif player_action.lower() == 'restart':
            print_wrapped("\nRestarting the game...", Fore.GREEN)
            last_response, game_state = start_game()
            continue
        
        print_wrapped("\nThinking...", Fore.GREEN)
        narrator_response = get_narrator_response(game_state, player_action, last_response)
        game_state = update_game_state(game_state, player_action, narrator_response)
        
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        print_wrapped(narrator_response, Fore.WHITE)
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        
        last_response = narrator_response

if __name__ == "__main__":
    main()
