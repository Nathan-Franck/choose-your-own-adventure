import re
import json
from typing import List, Dict, Any, Optional
import requests

class SimpleAdventureGame:
    def __init__(self, model_url: str = "http://localhost:1234/v1"):
        self.model_url = model_url
        self.game_state = {
            "inventory": [],
            "location": "starting_point",
            "status_effects": []
        }
        self.conversation_history = []
        
    def query_llm(self, prompt: str) -> str:
        """Send a prompt to the local LLM and get a response."""
        headers = {"Content-Type": "application/json"}
        
        # Include game state in the prompt
        game_state_str = (
            f"CURRENT GAME STATE:\n"
            f"Location: {self.game_state['location']}\n"
            f"Inventory: {', '.join(self.game_state['inventory']) if self.game_state['inventory'] else 'empty'}\n"
            f"Status Effects: {', '.join(self.game_state['status_effects']) if self.game_state['status_effects'] else 'none'}\n\n"
        )
        
        full_prompt = game_state_str + prompt
        
        # Prepare the messages including conversation history
        messages = self.conversation_history + [{"role": "user", "content": full_prompt}]
        
        payload = {
            "model": "local-model",  # Adjust based on your LM Studio setup
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(f"{self.model_url}/chat/completions", 
                                    headers=headers, 
                                    json=payload)
            response.raise_for_status()
            response_text = response.json()["choices"][0]["message"]["content"]
            
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            # Parse the response for game state changes
            self._parse_game_state_changes(response_text)
            
            # Return the cleaned response (without any state change commands)
            return self._clean_response(response_text)
        except Exception as e:
            print(f"Error querying LLM: {e}")
            return "Sorry, I encountered an error processing your request."
    
    def _parse_game_state_changes(self, response: str):
        """Parse the response for game state changes."""
        # Look for inventory additions
        add_items = re.findall(r'\[ADD_ITEM: (.*?)\]', response)
        for item in add_items:
            if item not in self.game_state["inventory"]:
                self.game_state["inventory"].append(item)
        
        # Look for inventory removals
        remove_items = re.findall(r'\[REMOVE_ITEM: (.*?)\]', response)
        for item in remove_items:
            if item in self.game_state["inventory"]:
                self.game_state["inventory"].remove(item)
        
        # Look for location changes
        location_changes = re.findall(r'\[SET_LOCATION: (.*?)\]', response)
        if location_changes:
            self.game_state["location"] = location_changes[-1]  # Use the last one if multiple
        
        # Look for status effect additions
        add_effects = re.findall(r'\[ADD_STATUS: (.*?)\]', response)
        for effect in add_effects:
            if effect not in self.game_state["status_effects"]:
                self.game_state["status_effects"].append(effect)
        
        # Look for status effect removals
        remove_effects = re.findall(r'\[REMOVE_STATUS: (.*?)\]', response)
        for effect in remove_effects:
            if effect in self.game_state["status_effects"]:
                self.game_state["status_effects"].remove(effect)
    
    def _clean_response(self, response: str) -> str:
        """Remove game state change commands from the response."""
        cleaned = re.sub(r'\[ADD_ITEM: .*?\]', '', response)
        cleaned = re.sub(r'\[REMOVE_ITEM: .*?\]', '', cleaned)
        cleaned = re.sub(r'\[SET_LOCATION: .*?\]', '', cleaned)
        cleaned = re.sub(r'\[ADD_STATUS: .*?\]', '', cleaned)
        cleaned = re.sub(r'\[REMOVE_STATUS: .*?\]', '', cleaned)
        return cleaned.strip()
    
    def start_game(self, scenario: str):
        """Start a new game with the given scenario."""
        self.conversation_history = [
            {"role": "system", "content": """
            You are the narrator of a silly choose-your-own-adventure game. 
            Your job is to create a fun, engaging, and slightly absurd adventure based on the scenario.
            
            Rules:
            1. Keep the tone light and humorous
            2. Maintain consistency in the story world
            3. Respond to player actions in a way that makes sense
            4. Keep players on-subject and only allow actions that make sense in the scenario
            5. Describe the scene vividly and give the player clear options
            
            To manage the game state, use these special commands in your response:
            - [ADD_ITEM: item name] - Add an item to the player's inventory
            - [REMOVE_ITEM: item name] - Remove an item from the player's inventory
            - [SET_LOCATION: location name] - Set the player's current location
            - [ADD_STATUS: status effect] - Add a status effect to the player
            - [REMOVE_STATUS: status effect] - Remove a status effect from the player
            
            When starting a new game, always set up the initial inventory with 3-5 items (some useful, some silly),
            set the initial location, and any starting status effects.
            
            Example of starting a game:
            [SET_LOCATION: Ant Colony Entrance]
            [ADD_ITEM: Tiny Wand]
            [ADD_ITEM: Dirt Cloak]
            [ADD_ITEM: Half-eaten Leaf]
            [ADD_STATUS: Magically Aware]
            
            You find yourself at the entrance of a massive ant colony. As a small worm, the towering dirt walls seem to stretch endlessly above you...
            
            These commands will be removed before showing the response to the player.
            """}
        ]
        
        # Reset game state
        self.game_state = {
            "inventory": [],
            "location": "starting_point",
            "status_effects": []
        }
        
        # Start the game with the given scenario
        return self.query_llm(f"Start a new adventure with this scenario: {scenario}")
    
    def player_action(self, action: str) -> str:
        """Process a player's action and return the narrator's response."""
        return self.query_llm(action)

def main():
    # Initialize the game
    game = SimpleAdventureGame()
    
    # Example scenario
    scenario = """
    You are a worm trapped in an ant colony, and you've just discovered you have magical 
    wizardry powers. Your task is to defeat the evil queen bee who has taken over the colony.
    Give the player a starting inventory with some useful items and some silly ones.
    """
    
    # Start the game
    response = game.start_game(scenario)
    print("Narrator:", response)
    print("\nCurrent Game State:")
    print(f"Location: {game.game_state['location']}")
    print(f"Inventory: {', '.join(game.game_state['inventory'])}")
    print(f"Status Effects: {', '.join(game.game_state['status_effects'])}")
    
    # Game loop
    while True:
        player_input = input("\nWhat do you want to do? (type 'quit' to exit): ")
        
        if player_input.lower() in ['quit', 'exit']:
            break
            
        response = game.player_action(player_input)
        print("\nNarrator:", response)
        print("\nCurrent Game State:")
        print(f"Location: {game.game_state['location']}")
        print(f"Inventory: {', '.join(game.game_state['inventory'])}")
        print(f"Status Effects: {', '.join(game.game_state['status_effects'])}")

if __name__ == "__main__":
    main()
