import json
import os
from typing import List, Dict, Any, Optional
import requests

class AdventureGame:
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
        
        # Prepare the messages including conversation history
        messages = self.conversation_history + [{"role": "user", "content": prompt}]
        
        # Define the available tools/functions the LLM can call
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_inventory",
                    "description": "Get the current inventory of the player",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_inventory",
                    "description": "Add an item to the player's inventory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string", "description": "The item to add"}
                        },
                        "required": ["item"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_from_inventory",
                    "description": "Remove an item from the player's inventory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string", "description": "The item to remove"}
                        },
                        "required": ["item"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_location",
                    "description": "Get the current location of the player",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_location",
                    "description": "Set the current location of the player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "The new location"}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_status_effects",
                    "description": "Get the current status effects on the player",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_status_effect",
                    "description": "Add a status effect to the player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "effect": {"type": "string", "description": "The status effect to add"}
                        },
                        "required": ["effect"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_status_effect",
                    "description": "Remove a status effect from the player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "effect": {"type": "string", "description": "The status effect to remove"}
                        },
                        "required": ["effect"]
                    }
                }
            }
        ]
        
        payload = {
            "model": "gemma-3-4b-it", # Adjust based on your LM Studio setup
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto"
        }
        
        try:
            response = requests.post(f"{self.model_url}/chat/completions", 
                                    headers=headers, 
                                    json=payload)
            response.raise_for_status()
            return self._process_response(response.json())
        except Exception as e:
            print(f"Error querying LLM: {e}")
            return "Sorry, I encountered an error processing your request."
    
    def _process_response(self, response_data: Dict[str, Any]) -> str:
        """Process the LLM response, handling any tool calls."""
        response_message = response_data["choices"][0]["message"]
        
        # Add the assistant's message to history
        self.conversation_history.append({"role": "assistant", "content": response_message.get("content", "")})
        
        # Check if there are tool calls to process
        if "tool_calls" in response_message:
            for tool_call in response_message["tool_calls"]:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                # Execute the appropriate function
                result = self._execute_function(function_name, function_args)
                
                # Add the function result to the conversation
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": function_name,
                    "content": json.dumps(result)
                })
            
            # Get a follow-up response from the LLM with the tool results
            return self.query_llm("Continue with your response based on the tool results.")
        
        return response_message.get("content", "")
    
    def _execute_function(self, function_name: str, args: Dict[str, Any]) -> Any:
        """Execute a function called by the LLM."""
        if function_name == "get_inventory":
            return self.game_state["inventory"]
        
        elif function_name == "add_to_inventory":
            item = args.get("item")
            if item and item not in self.game_state["inventory"]:
                self.game_state["inventory"].append(item)
            return {"added": item, "inventory": self.game_state["inventory"]}
        
        elif function_name == "remove_from_inventory":
            item = args.get("item")
            if item and item in self.game_state["inventory"]:
                self.game_state["inventory"].remove(item)
            return {"removed": item, "inventory": self.game_state["inventory"]}
        
        elif function_name == "get_location":
            return {"location": self.game_state["location"]}
        
        elif function_name == "set_location":
            location = args.get("location")
            if location:
                self.game_state["location"] = location
            return {"location": self.game_state["location"]}
        
        elif function_name == "get_status_effects":
            return {"status_effects": self.game_state["status_effects"]}
        
        elif function_name == "add_status_effect":
            effect = args.get("effect")
            if effect and effect not in self.game_state["status_effects"]:
                self.game_state["status_effects"].append(effect)
            return {"added": effect, "status_effects": self.game_state["status_effects"]}
        
        elif function_name == "remove_status_effect":
            effect = args.get("effect")
            if effect and effect in self.game_state["status_effects"]:
                self.game_state["status_effects"].remove(effect)
            return {"removed": effect, "status_effects": self.game_state["status_effects"]}
        
        return {"error": "Unknown function"}
    
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
            5. Use the available tools to manage the player's inventory, location, and status effects
            6. Always initialize the game by setting up the player's starting inventory, location, and any status effects
            7. Describe the scene vividly and give the player clear options
            8. If the player checks their inventory, use the get_inventory tool
            
            When narrating, be creative but maintain the logic of the game world.
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
    game = AdventureGame()
    
    # Example scenario
    scenario = """
    You are a worm trapped in an ant colony, and you've just discovered you have magical 
    wizardry powers. Your task is to defeat the evil queen bee who has taken over the colony.
    Give the player a starting inventory with some useful items and some silly ones.
    """
    
    # Start the game
    response = game.start_game(scenario)
    print("Narrator:", response)
    
    # Game loop
    while True:
        player_input = input("\nWhat do you want to do? (type 'quit' to exit): ")
        
        if player_input.lower() in ['quit', 'exit']:
            break
            
        response = game.player_action(player_input)
        print("\nNarrator:", response)

if __name__ == "__main__":
    main()

