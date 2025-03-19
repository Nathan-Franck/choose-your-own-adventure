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
        self.last_narration = ""
        
    def query_llm(self, prompt: str) -> str:
        """Send a prompt to the local LLM and get a response."""
        headers = {"Content-Type": "application/json"}
        
        # Create a simple system instruction with XML tags
        system_instructions = """
        You are the narrator of a silly choose-your-own-adventure game.
        
        IMPORTANT RULES:
        1. Keep the tone light and humorous
        2. Respond directly to the player's action
        3. Keep your responses under 200 words
        4. DO NOT restart the scene - continue from where we left off
        5. If the player wants to check inventory, show them their items
        6. If the player wants to use an item, let them if it makes sense
        7. If the player wants to discard an item, remove it from their inventory
        8. If the player finds a new item, add it to their inventory
        
        Use these commands in your response (they will be processed by the game engine):
        - <add_item>item name</add_item> - Add an item to inventory
        - <remove_item>item name</remove_item> - Remove an item from inventory
        - <set_location>location name</set_location> - Change the player's location
        - <add_status>status name</add_status> - Add a status effect
        - <remove_status>status name</remove_status> - Remove a status effect
        """
        
        # Create a simple game state description
        game_state_str = (
            f"CURRENT GAME STATE:\n"
            f"- Location: {self.game_state['location']}\n"
            f"- Inventory: {', '.join(self.game_state['inventory']) if self.game_state['inventory'] else 'empty'}\n"
            f"- Status Effects: {', '.join(self.game_state['status_effects']) if self.game_state['status_effects'] else 'none'}\n\n"
        )
        
        # Include the last narration for context
        context = ""
        if self.last_narration:
            context = f"PREVIOUS NARRATION:\n{self.last_narration}\n\n"
        
        # Combine everything into a single prompt
        full_prompt = f"{system_instructions}\n\n{game_state_str}{context}PLAYER ACTION: {prompt}\n\nNARRATOR RESPONSE:"
        
        # Create a simple message structure
        messages = [{"role": "user", "content": full_prompt}]
        
        payload = {
            "model": "local-model",
            "messages": messages,
            "temperature": 0.5,  # Lower temperature for more consistent responses
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                f"{self.model_url}/chat/completions", 
                headers=headers, 
                json=payload,
                timeout=4 * 60
            )
            
            if response.status_code == 200:
                response_text = response.json()["choices"][0]["message"]["content"]
                
                # Update the game state based on commands in the response
                self._update_game_state(response_text)
                
                # Save this narration for context in the next turn
                self.last_narration = response_text
                
                # Return the raw response without cleaning
                return response_text
            else:
                print(f"Error status code: {response.status_code}")
                print(f"Response content: {response.text}")
                return "Sorry, I encountered an error processing your request."
                
        except Exception as e:
            print(f"Error querying LLM: {e}")
            return "Sorry, I encountered an error processing your request."
    
    def _update_game_state(self, response: str):
        """Update the game state based on XML commands in the response."""
        # Look for inventory additions
        add_items = re.findall(r'<add_item>(.*?)</add_item>', response, re.DOTALL)
        for item in add_items:
            item = item.strip()
            if item and item not in self.game_state["inventory"]:
                self.game_state["inventory"].append(item)
        
        # Look for inventory removals
        remove_items = re.findall(r'<remove_item>(.*?)</remove_item>', response, re.DOTALL)
        for item in remove_items:
            item = item.strip()
            if item:
                # Try to find a close match if not exact
                for inv_item in self.game_state["inventory"]:
                    if item.lower() in inv_item.lower() or inv_item.lower() in item.lower():
                        self.game_state["inventory"].remove(inv_item)
                        break
        
        # Look for location changes
        location_changes = re.findall(r'<set_location>(.*?)</set_location>', response, re.DOTALL)
        if location_changes:
            self.game_state["location"] = location_changes[-1].strip()
        
        # Look for status effect additions
        add_effects = re.findall(r'<add_status>(.*?)</add_status>', response, re.DOTALL)
        for effect in add_effects:
            effect = effect.strip()
            if effect and effect not in self.game_state["status_effects"]:
                self.game_state["status_effects"].append(effect)
        
        # Look for status effect removals
        remove_effects = re.findall(r'<remove_status>(.*?)</remove_status>', response, re.DOTALL)
        for effect in remove_effects:
            effect = effect.strip()
            if effect and effect in self.game_state["status_effects"]:
                self.game_state["status_effects"].remove(effect)
    
    def start_game(self, scenario: str):
        """Start a new game with the given scenario."""
        # Reset game state
        self.game_state = {
            "inventory": [],
            "location": "starting_point",
            "status_effects": []
        }
        self.last_narration = ""
        
        # Start the game with the given scenario
        start_prompt = f"""
        You are starting a new silly text-adventure game with this scenario:
        
        {scenario}
        
        Begin by:
        1. Setting the starting location using <set_location>location name</set_location>
        2. Adding 3-4 items to the player's inventory using <add_item>item name</add_item>
        3. Adding any starting status effects using <add_status>status effect</add_status>
        
        Then describe the opening scene, any interesting details, and ask the player what they'd like to do next.
        """
        
        return self.query_llm(start_prompt)
    
    def player_action(self, action: str) -> str:
        """Process a player's action and return the narrator's response."""
        # Special handling for inventory management
        if action.lower() in ["inventory", "check inventory", "what do i have"]:
            items = ", ".join(self.game_state["inventory"]) if self.game_state["inventory"] else "nothing"
            return f"You check your inventory and find: {items}."
        
        if action.lower().startswith("discard ") or action.lower().startswith("drop "):
            item_to_discard = action.lower().replace("discard ", "").replace("drop ", "")
            for item in self.game_state["inventory"]:
                if item_to_discard in item.lower():
                    self.game_state["inventory"].remove(item)
                    return f"You discard the {item}."
            return f"You don't have a {item_to_discard} to discard."
        
        # Normal action processing
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
