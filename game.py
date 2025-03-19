import re
import json
import requests
import time

class SimpleAdventureGame:
    def __init__(self, model_url: str = "http://localhost:1234/v1"):
        self.model_url = model_url
        self.game_state = {
            "inventory": [],
            "location": "none",
            "status_effects": []
        }
        self.last_narration = ""
        
    def query_llm(self, prompt: str) -> str:
        """Send a prompt to the local LLM and get a response."""
        headers = {"Content-Type": "application/json"}
        
        # Create a simple system instruction with XML tags
        system_instructions = """
        You are the narrator of a silly text adventure game.
        
        IMPORTANT RULES:
        1. Keep the tone light and humorous
        2. Respond directly to the player's action
        3. Keep your responses under 200 words
        
        During your response, you please wrap all key words in game tags to affect the state of the game.
        - <takeItem>item name</takeItem> - Add an item to inventory
        - <discardItem>item name</discardItem> - Remove an item from inventory
        - <goToLocation>location name</goToLocation> - Change the player's location
        - <aquireStatus>status name</aquireStatus> - Add a status effect
        - <dispellStatus>status name</dispellStatus> - Remove a status effect
        """

        final_reminder = """
        Remember to keep using game tags, including items, location and status!
        These are the valid tags:
            takeItem, discardItem, goToLocation, aquireStatus, dispellStatus
        Any other tags aren't real and serve no purpose.
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
        full_prompt = f"{system_instructions}\n\n{game_state_str}{context}{final_reminder}\n\nPLAYER ACTION: {prompt}\n\nNARRATOR RESPONSE:"
        
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
        add_items = re.findall(r'<takeItem>(.*?)</takeItem>', response, re.DOTALL)
        for item in add_items:
            item = item.strip()
            if item and item not in self.game_state["inventory"]:
                self.game_state["inventory"].append(item)
        
        # Look for inventory removals
        remove_items = re.findall(r'<discardItem>(.*?)</discardItem>', response, re.DOTALL)
        for item in remove_items:
            item = item.strip()
            if item:
                # Try to find a close match if not exact
                for inv_item in self.game_state["inventory"]:
                    if item.lower() in inv_item.lower() or inv_item.lower() in item.lower():
                        self.game_state["inventory"].remove(inv_item)
                        break
        
        # Look for location changes
        location_changes = re.findall(r'<goToLocation>(.*?)</goToLocation>', response, re.DOTALL)
        if location_changes:
            self.game_state["location"] = location_changes[-1].strip()
        
        # Look for status effect additions
        add_effects = re.findall(r'<aquireStatus>(.*?)</aquireStatus>', response, re.DOTALL)
        for effect in add_effects:
            effect = effect.strip()
            if effect and effect not in self.game_state["status_effects"]:
                self.game_state["status_effects"].append(effect)
        
        # Look for status effect removals
        remove_effects = re.findall(r'<dispellStatus>(.*?)</dispellStatus>', response, re.DOTALL)
        for effect in remove_effects:
            effect = effect.strip()
            if effect and effect in self.game_state["status_effects"]:
                self.game_state["status_effects"].remove(effect)
    
    def start_game(self, scenario: str):
        """Start a new game with the given scenario."""
        # Reset game state
        self.game_state = {
            "inventory": [],
            "location": "none",
            "status_effects": []
        }
        self.last_narration = ""
        
        # Start the game with the given scenario
        start_prompt = f"""
        You are the narrator of a silly text adventure game.
        
        IMPORTANT RULES:
        1. Keep the tone light and humorous
        2. Respond directly to the player's action
        3. Keep your responses under 200 words
        
        During your response, you please wrap all key words in these game tags to affect the state of the game.
        They should be used whenever appropriate in the course of your natural response.
        - <takeItem>item name</takeItem> - Add an item to inventory
        - <discardItem>item name</discardItem> - Remove an item from inventory
        - <goToLocation>location name</goToLocation> - Change the player's location
        - <aquireStatus>status name</aquireStatus> - Add a status effect
        - <dispellStatus>status name</dispellStatus> - Remove a status effect
        
        SCENARIO: {scenario}
        
        Begin by:
        1. Establishing the starting location, with any intersting details
        2. Describing 3-4 items in the player's inventory, they could be useful or not!
        3. Specifying any starting status effects (who or what they are should also be considered a status)
        Remember to keep using game tags, including items, location and status!
        These are the valid tags:
            takeItem, discardItem, goToLocation, aquireStatus, dispellStatus
        Any other tags aren't real and serve no purpose.
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
