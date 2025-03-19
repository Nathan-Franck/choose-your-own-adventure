import re
import json
import requests
import time

class SimpleAdventureGame:
    def __init__(self, model_url: str = "http://localhost:1234/v1"):
        self.model_url = model_url
        self.game_state = {
            "inventory": [],
            "location": "starting_point",
            "status_effects": []
        }
        self.story_so_far = ""  # We'll use this instead of conversation history
        
    def query_llm(self, prompt: str) -> str:
        """Send a prompt to the local LLM and get a response."""
        headers = {"Content-Type": "application/json"}
        
        # Include game state and story so far in the prompt
        system_instructions = """
        You are the narrator of a silly choose-your-own-adventure game.
        Keep the tone light and humorous. Respond to player actions in a way that makes sense.
        Keep your responses concise (under 300 words).
        
        To manage the game state, use these special commands in your response:
        - [ADD_ITEM: item name] - Add an item to the player's inventory
        - [REMOVE_ITEM: item name] - Remove an item from the player's inventory
        - [SET_LOCATION: location name] - Set the player's current location
        - [ADD_STATUS: status effect] - Add a status effect to the player
        - [REMOVE_STATUS: status effect] - Remove a status effect from the player
        """
        
        game_state_str = (
            f"CURRENT GAME STATE:\n"
            f"Location: {self.game_state['location']}\n"
            f"Inventory: {', '.join(self.game_state['inventory']) if self.game_state['inventory'] else 'empty'}\n"
            f"Status Effects: {', '.join(self.game_state['status_effects']) if self.game_state['status_effects'] else 'none'}\n\n"
        )
        
        # Include a condensed version of the story so far
        story_context = ""
        if self.story_so_far:
            story_context = f"STORY SO FAR:\n{self.story_so_far}\n\n"
        
        full_prompt = f"{system_instructions}\n\n{game_state_str}{story_context}PLAYER ACTION: {prompt}\n\nNARRATOR RESPONSE:"
        
        # Simple message structure with just one user message
        messages = [{"role": "user", "content": full_prompt}]
        
        payload = {
            "model": "local-model",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800
        }
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.post(
                    f"{self.model_url}/chat/completions", 
                    headers=headers, 
                    json=payload,
                    timeout=4 * 60
                )
                
                if response.status_code == 200:
                    response_text = response.json()["choices"][0]["message"]["content"]
                    
                    # Parse the response for game state changes
                    self._parse_game_state_changes(response_text)
                    
                    # Clean the response
                    cleaned_response = self._clean_response(response_text)
                    
                    # Update the story so far (keep it manageable)
                    if len(self.story_so_far) > 1000:  # Limit to ~1000 chars
                        self.story_so_far = self.story_so_far[-500:]  # Keep the last 500 chars
                    
                    # Add a summary of this exchange to the story
                    self.story_so_far += f"Player: {prompt}\nNarrator: {cleaned_response[:100]}...\n"
                    
                    return cleaned_response
                else:
                    print(f"Error status code: {response.status_code}")
                    print(f"Response content: {response.text}")
                    retry_count += 1
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Error querying LLM (attempt {retry_count+1}/{max_retries}): {e}")
                retry_count += 1
                time.sleep(1)
        
        # If we get here, all retries failed
        return "Sorry, I encountered an error processing your request. Let's continue our adventure. What would you like to do next?"
    
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
        # Reset game state
        self.game_state = {
            "inventory": [],
            "location": "starting_point",
            "status_effects": []
        }
        self.story_so_far = ""
        
        # Start the game with the given scenario
        start_prompt = f"""
        You are starting a new silly choose-your-own-adventure game with this scenario:
        
        {scenario}
        
        Begin by setting up the initial game state:
        1. Set the starting location using [SET_LOCATION: location name]
        2. Add 3-5 items to the player's inventory (mix of useful and silly items) using [ADD_ITEM: item name]
        3. Add any starting status effects using [ADD_STATUS: status effect]
        
        Then describe the opening scene vividly and give the player 2-3 clear options for what to do next.
        Keep your response under 300 words and make it fun and engaging!
        """
        
        return self.query_llm(start_prompt)
    
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
    
    print("Starting your adventure... (this may take a moment)")
    
    # Start the game
    response = game.start_game(scenario)
    print("\nNarrator:", response)
    print("\nCurrent Game State:")
    print(f"Location: {game.game_state['location']}")
    print(f"Inventory: {', '.join(game.game_state['inventory'])}")
    print(f"Status Effects: {', '.join(game.game_state['status_effects'])}")
    
    # Game loop
    while True:
        player_input = input("\nWhat do you want to do? (type 'quit' to exit): ")
        
        if player_input.lower() in ['quit', 'exit']:
            break
        
        print("Thinking...")
        response = game.player_action(player_input)
        print("\nNarrator:", response)
        print("\nCurrent Game State:")
        print(f"Location: {game.game_state['location']}")
        print(f"Inventory: {', '.join(game.game_state['inventory'])}")
        print(f"Status Effects: {', '.join(game.game_state['status_effects'])}")

if __name__ == "__main__":
    main()
