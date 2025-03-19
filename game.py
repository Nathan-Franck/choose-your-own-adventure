import requests
import xml.etree.ElementTree as ET
import re
import os
import textwrap
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored terminal output
init()

# LM Studio API endpoint
API_URL = "http://192.168.1.74:1234/v1/chat/completions"

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

def call_llm(messages, temperature=0.7, max_tokens=1024):
    """Call the LM Studio API with the given messages."""
    try:
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
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error calling LM Studio API: {e}")
        return None

def generate_scenario():
    """Generate the initial game scenario."""
    scenario_prompt = """
    You are the creator of a silly, light-hearted text adventure game. 
    Create a fun starting scenario with the following:
    1. Who/what the player is (could be a normal person, a wizard, a talking animal, etc.)
    2. Where they are starting their adventure
    3. What items they have in their inventory (2-4 items)
    4. A brief description of the surroundings and situation
    
    Make it humorous and whimsical. Don't be too verbose, just a paragraph or two.
    """
    
    messages = [{"role": "user", "content": scenario_prompt}]
    scenario = call_llm(messages, temperature=0.9)
    return scenario

def initialize_game_state(scenario):
    """Initialize the XML game state based on the scenario."""
    # Create base XML structure
    root = ET.Element("game-state")
    player = ET.SubElement(root, "player-character", {"being-type": "unknown", "location": "unknown"})
    inventory = ET.SubElement(player, "inventory")
    status = ET.SubElement(player, "status-effects")
    
    # Extract information from scenario using the state aggregator
    state_prompt = f"""
    Based on this initial scenario description:
    
    "{scenario}"
    
    Update this XML game state to reflect the character type, location, and inventory items:
    
    <game-state>
    <player-character being-type="none" location="none">
    <inventory>
    </inventory>
    <status-effects>
    </status-effects>
    </player-character>
    </game-state>
    
    Return ONLY the updated XML, nothing else.
    """
    
    messages = [{"role": "user", "content": state_prompt}]
    xml_response = call_llm(messages, temperature=0.2)
    
    # Extract XML from response
    xml_match = re.search(r'<game-state>.*?</game-state>', xml_response, re.DOTALL)
    if xml_match:
        return xml_match.group(0)
    else:
        # Fallback if XML extraction fails
        return ET.tostring(root, encoding='unicode')

def update_game_state(current_state, narrator_response):
    """Update the game state based on the narrator's response."""
    state_prompt = f"""
    Given the current game state:
    
    {current_state}
    
    And the narrator's latest response:
    
    "{narrator_response}"
    
    Update the XML game state to reflect any changes that occurred in the narrator's response:
    - Changes in location
    - Items added or removed from inventory
    - New status effects applied or removed
    - Any other state changes implied by the narrative
    
    Return ONLY the updated XML, nothing else.
    """
    
    messages = [{"role": "user", "content": state_prompt}]
    xml_response = call_llm(messages, temperature=0.2)
    
    # Extract XML from response
    xml_match = re.search(r'<game-state>.*?</game-state>', xml_response, re.DOTALL)
    if xml_match:
        return xml_match.group(0)
    else:
        # Fallback if XML extraction fails
        return current_state

def get_narrator_response(current_state, player_action, last_response=None):
    """Get the narrator's response to the player's action."""
    context = ""
    if last_response:
        context = f"Your last narration was: \"{last_response}\"\n\n"
    
    narrator_prompt = f"""
    {context}The current game state is:
    
    {current_state}
    
    The player's action is: "{player_action}"
    
    As the narrator of this silly, light-hearted text adventure game, describe what happens next.
    Be creative, humorous, and engaging. Keep your response to 2-3 paragraphs at most.
    Remember that players can:
    - Move around
    - Talk to people and animals
    - Use items from their inventory
    - Interact with the environment
    
    Don't list options explicitly - let the player decide what to do next naturally.
    """
    
    messages = [{"role": "user", "content": narrator_prompt}]
    return call_llm(messages, temperature=0.8)

def main():
    clear_screen()
    print_wrapped("Welcome to Silly Text Adventure!", Fore.CYAN)
    print_wrapped("Type 'quit' at any time to exit the game.\n", Fore.YELLOW)
    
    print_wrapped("Generating your adventure...", Fore.GREEN)
    scenario = generate_scenario()
    game_state = initialize_game_state(scenario)
    
    print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
    print_wrapped(scenario, Fore.WHITE)
    print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
    
    last_response = scenario
    
    while True:
        print_wrapped("What would you like to do?", Fore.YELLOW)
        player_action = input("> ")
        
        if player_action.lower() in ['quit', 'exit', 'q']:
            print_wrapped("\nThanks for playing!", Fore.CYAN)
            break
        
        print_wrapped("\nThinking...", Fore.GREEN)
        narrator_response = get_narrator_response(game_state, player_action, last_response)
        game_state = update_game_state(game_state, narrator_response)
        
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        print_wrapped(narrator_response, Fore.WHITE)
        print_wrapped("\n" + "="*80 + "\n", Fore.CYAN)
        
        last_response = narrator_response

if __name__ == "__main__":
    main()
