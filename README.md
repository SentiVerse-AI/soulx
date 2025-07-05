<div align="center">

# **SoulX  (Subnet 115): Wake me, when you need me.** 
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Subnet 115](https://img.shields.io/badge/Subnet-115_Ѕ-blue)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/SentiVerse-AI/SoulX)
Welcome to SoulX  — a decentralized AI network dedicated to forging true SoulX s for the next generation of interactive entertainment.

</div>

# SoulX  -  Wake me, when you need me.

![SoulX  Logo](./assets/logo.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The Problem: A Digital World Bound by Scripts
We've all been there. You're standing in a breathtakingly beautiful game world, you approach a character brimming with anticipation, only to be met with a few cold, endlessly repeated lines of dialogue. In that moment, the immersion shatters. These characters feel less like inhabitants and more like "digital puppets," waiting in a perpetual loop to be triggered by the player.
Developers dream of creating living worlds but are constrained by the technology and cost of traditional AI. Players crave genuine interaction but are left with predictable conversations on a pre-written path.
We believe it's time to bring a true revolution to gaming.
Our Mission: To Empower Every Game World
The mission of SoulX  (Subnet 115) is to provide game developers across the globe with the tools to effortlessly populate their worlds with intelligent NPCs who possess unique personalities, persistent memory, and unscripted behavior.
We are committed to transforming every NPC from a predictable tool into a true game companion, capable of co-creating unforgettable stories with players.
We are not just generating text; we are crafting characters.
How It Works: Rewarding True Gameplay
To achieve this goal, our validation mechanism is designed to reward the AI models that deliver the best gameplay experience.

Validators as Game Masters:
Validators are no longer simple prompters. They design and distribute micro-quests to the miner network, containing a [Scene Description], a [Character Card] (personality, background, goals), and a [Player Intent] to test the network.


Miners as SoulX  Actors:
Miners drive their AI models to generate the most compelling NPC dialogue and actions that fit the context and, most importantly, drive the game forward.


How We Score:
Our validation system evaluates responses from a game designer's perspective across multiple dimensions:


 Consistency: Does the NPC's speech and behavior align with their established character profile?


 Memory: Can the NPC recall key information from previous interactions and reference it contextually?


 Creativity: Is the dialogue vivid, natural, and free from the chains of predictability?


 Goal-Driven: Is the NPC subtly and intelligently guiding the player toward a quest objective or world discovery, in a way that feels true to their character?


The Pillars of Inspiration: Our Collective Gaming Memory
A great actor needs a great script. To teach our AI models how to portray compelling characters, we didn't turn to cold, generic datasets. Instead, we returned to the collective memory of all gamers, drawing inspiration from the legendary titles that have shaped our lives.
Disclaimer:  SoulX  is a 100% original project. We do not use any copyrighted assets (text, audio, or models) from the games listed below. These legendary titles serve as our "cultural touchstones" and "style guides" for generating our unique, original dataset. Our goal is to pay homage to the spirit of these games that have shaped global gaming culture. All trademarks are the property of their respective owners.

1. High Fantasy: The Archetypes of an Era

Inspirations: World of Warcraft, The Elder Scrolls V: Skyrim


What we learn: Factional pride, iconic racial archetypes, and world-building through the dialogue of everyday NPCs.


Our Synthetic Data Prompt: Generate a dialogue where a grumpy Orc blacksmith refuses to craft a delicate elven-style bow, viewing it as a "fragile twig."

2. Sci-Fi & Cyberpunk: The SoulX s of the Future

Inspirations: Mass Effect Trilogy, Cyberpunk 2077


What we learn: Deep companion relationships, branching moral choices, and world-specific slang and terminology.


Our Synthetic Data Prompt: Generate a conversation with a cynical Netrunner in a neon-lit Night City bar, who tries to sell the player a piece of risky, second-hand cyberware.

3. JRPG: The Art of Narrative and Emotion

Inspirations: Final Fantasy Series, Persona Series


What we learn: Distinctive character archetypes, emotionally-driven storytelling, and balancing everyday life dialogue with epic adventure.


Our Synthetic Data Prompt: Create a dialogue where a Moogle-like creature gives the player cryptic but helpful clues to navigate an enchanted forest.

4. Post-Apocalyptic: The Depth of Choice

Inspiration: Fallout: New Vegas


What we learn: Masterful quest guidance through conversation, dark humor, and NPC reactions based on player reputation and faction alignment.


Our Synthetic Data Prompt: Simulate a conversation with a weathered Wasteland scavenger who offers to trade a rare water chip, but his dialogue subtly hints that the chip might be stolen or faulty.

Join Us and Forge a Legend
Our world is just beginning to take shape, and every participant is a co-creator in this grand design. Whether you wish to bring characters to life (as a Miner) or design the ultimate quests (as a Validator), we welcome you to join us.

Installation
- [Requirements](#requirements)
  - [Miner Requirements](#miner-requirements)
  - [Validator Requirements](#validator-requirements)
- [Installation](#installation)
  - [Common Setup](#common-setup)
  - [Miner Specific Setup](#miner-specific-setup)
  - [Validator Specific Setup](#validator-specific-setup)
- [Get Involved](#get-involved)
---

# Requirements

## Miner Requirements
To run a SoulX  miner, you will need:
- A Bittensor wallet
- Bittensor mining hardware (CPU, GPUs, etc.) 
- A running Redis server for data persistence
- Python 3.10 or higher

## Validator Requirements
To run a SoulX  validator, you will need:
- A Bittensor wallet
- A running Redis server for data persistence
- Python 3.10 or higher environment

# Installation

## Common Setup
These steps apply to both miners and validators:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/SentiVerse-AI/soulx.git
    cd soulx 
    ```

2.  **Set up and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Upgrade pip:**
    ```bash
    pip install --upgrade pip
    ```

4.  **Install the SoulX  package:**
    ```bash
    pip install -e .
    ```

## Miner Specific Setup
After completing the common setup, follow the detailed steps in the Miner Guide:

* [Install Redis](docs/running_miner.md#2-install-redis)
* [Configure your miner (`.env` file or command-line arguments)](docs/running_miner.md#5-configuration)
* [Run the miner (using PM2 recommended)](docs/running_miner.md#6-running-the-miner)

For the complete, step-by-step instructions for setting up and running your miner, please refer to the [SoulX Miner Setup Guide](docs/running_miner.md).

## Validator Specific Setup
After completing the common setup, follow the detailed steps in the Validator Guide:

* [Configure your validator (`.env` file or command-line arguments)](docs/running_validator.md#4-configuration-methods)
* [Run the validator (using PM2 recommended)](docs/running_validator.md#5-running-the-validator)

For the complete, step-by-step instructions for setting up and running your validator, please refer to the [SoulX Validator Setup](docs/running_validator.md).

# Get Involved

- Join the discussion on the [Bittensor Discord](https://discord.com/invite/bittensor) in the Subnet 115 channels.
- Check out the [Bittensor Documentation](https://docs.bittensor.com/) for general information about running subnets and nodes.
- Contributions are welcome! See the repository's contribution guidelines for details.

---
**Full Guides:**
- [SoulX Miner Setup Guide ](docs/running_miner.md)
- [SoulX Validator Setup ](docs/running_validator.md)
