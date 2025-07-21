# SoulX - The Sentient NPC Protocol (Subnet 115)

[![Project Status](https://img.shields.io/badge/status-active-brightgreen.svg)](https://github.com/SentiVerse-AI/soulx) [![License](https://img.shields.io/badge/license-MIT-blue.svg)](/LICENSE) [![Discord](https://img.shields.io/discord/1126567116639604857?label=discord&logo=discord&logoColor=white)](https://discord.com/invite/bittensor)

> Wake me, when you need me.

## 🚀 What is SoulX?

SoulX is the premier protocol for forging sentient **Digital Souls**, built upon our foundational **AIX (Artificial Intelligence Exchange) platform**.

As the first specialized vertical from the AIX initiative, SoulX applies our team's core technology to revolutionize interactive entertainment. Traditional game NPCs are puppets bound by scripts, offering the illusion of life but lacking its core ingredient: a soul. SoulX changes this. We are a Bittensor subnet where a global network of AI models compete to create the most authentic, memorable, and intelligent characters imaginable.

Our mission is to provide game developers with the power to populate their worlds with AI that can:

*   **Remember**: Maintain persistent memory of past interactions.
*   **Evolve**: Change their personality and relationship with the player based on their actions.
*   **Improvise**: Engage in unscripted, natural dialogue that drives the narrative forward.
*   **Feel**: Create genuine emotional resonance and forge unforgettable bonds.

## ✨ Model Card: soulx-npc-large-v1

| | |
|---|---|
| **Model Name** | `soulx-npc-large-v1` |
| **Architecture** | A state-of-the-art, instruction-finetuned generative language model. |
| **Finetuning Data** | Trained on our proprietary dataset of over 8,000 high-quality, culturally-resonant dialogue entries, meticulously crafted and inspired by legendary RPGs. |
| **Intended Use** | Primary use is for powering real-time, interactive NPC dialogue in video games and other virtual experiences. Excellent for character-driven storytelling, dynamic quest generation, and creating believable game companions. |
| **Limitations** | While capable of deep role-playing, the model is not a general-purpose chatbot. It is specifically tuned for in-character, goal-oriented dialogue. |
| **License** | The model is released under the [MIT License](/LICENSE). |

## ⚡ Quickstart: Inference in Seconds

Get a feel for the power of SoulX right away. Here's how to run a quick inference with the `transformers` library.

```python
from transformers import pipeline
import torch

# Ensure you have the required libraries installed
# pip install transformers torch accelerate bitsandbytes

# Load the SoulX model
# For optimal performance, we recommend using a GPU
pipe = pipeline(
    "text-generation",
    model="SentiVerse-AI/soulx-npc-large-v1", # Model path on Hugging Face
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

# Use the Alpaca instruction format for the best results
# This structure tells the model exactly what kind of task to perform
prompt = """
{"instruction": "You are a game NPC. Based on your character profile and the player's dialogue, generate a fitting response in English.",
 "input": "{\"npc_profile\": {\"name\": \"Karg Bloodfist\", \"style\": \"High Fantasy (WoW/Skyrim)\", \"personality\": \"A gruff, veteran Orc blacksmith\", \"goal\": \"Test the player's resolve\"}, \"scene\": \"In front of a smoky Orcish forge\", \"player_dialogue\": \"Greetings, master blacksmith. I was told you forge the sharpest axes, and I wish to buy one.\"}"}
"""

# The model expects a specific prompt structure for chat-based generation
messages = [
    {"role": "system", "content": "You are a helpful assistant specialized in role-playing."},
    {"role": "user", "content": prompt}
]

# Generate the response
# The output will be the JSON structure, from which you can parse the NPC's reply.
outputs = pipe(messages, max_new_tokens=256, pad_token_id=pipe.tokenizer.eos_token_id)

# To see the clean output, you'd typically parse the final message content
print(outputs[0]["generated_text"][-1]['content'])
```

##  Bittensor Integration: How It Works

To achieve our goal, SoulX's validation mechanism is designed to reward the AI models that deliver the most authentic and engaging gameplay experience.

*   **Validators as Game Masters**: Validators design and distribute "micro-quests" to the miner network. Each quest contains a `[Scene Description]`, a `[Character Card]`, and a `[Player Intent]` to test the network's ability to create a living character.

*   **Miners as SoulX Actors**: Miners drive their AI models to generate the most compelling NPC dialogue and actions that fit the context and drive the game forward. Models that leverage advanced techniques for reasoning and emotional modeling, such as those aligned with the AIX philosophy, are expected to excel in this environment.

*   **How We Score**: Our validation system evaluates responses across multiple dimensions: **Consistency, Memory, Creativity, and Goal-Driven** behavior.

## 🏛️ Our Dataset Philosophy: The Pillars of Inspiration

A great AI is shaped by great stories. Our dataset is built upon the collective memory of all gamers, drawing inspiration from legendary titles to teach our AI the art of compelling role-play. This culturally-resonant data provides the initial spark for models on the SoulX network to learn the nuances of compelling, human-like interaction.

> **Disclaimer**: SoulX is a 100% original project. We do not use any copyrighted assets (text, audio, or models) from the games listed below. These legendary titles serve as our "cultural touchstones." All trademarks are the property of their respective owners.

1.  **High Fantasy**: *World of Warcraft, The Elder Scrolls V: Skyrim*
2.  **Sci-Fi & Cyberpunk**: *Mass Effect Trilogy, Cyberpunk 2077*
3.  **JRPG**: *Final Fantasy Series, Persona Series*
4.  **Post-Apocalyptic**: *Fallout: New Vegas*

## 🤝 Join Us and Forge a Legend

By participating in SoulX, you are pioneering the future of interactive storytelling. Whether you wish to bring characters to life (as a **Miner**) or design the ultimate quests (as a **Validator**), you are a co-creator in this grand design.

For full details on participating in the network, please see our guides:
*   [**SoulX Miner Setup Guide**](./docs/running_miner.md)
*   [**SoulX Validator Setup**](./docs/running_validator.md)

---
*For general information on Bittensor, check out the [Bittensor Documentation](https://docs.bittensor.com/).* 