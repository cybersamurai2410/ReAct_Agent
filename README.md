# ReAct_Agent
Implemented ReAct (React + Act) agentic architecture allowing an LLM to demonstrate Chain-of-Thought reasoning with access to tools for a given prompt.

## Example Run
**Prompt:** *"What is the square root of mass of the earth multiplied by 10?"*
```bash
Thought: I need to find the mass of Earth on Wikipedia
Action: wikipedia: mass of earth
PAUSE
[('wikipedia', 'mass of earth')]
Observation: <span class="searchmatch">Earth</span> <span class="searchmatch">mass</span> (denoted as M🜨, M♁ or ME, where 🜨 and ♁ are
the astronomical symbols for <span class="searchmatch">Earth</span>), is a unit <span class="searchmatch">of</span> <span class="searchmatch">mass</span> equal to the <span class="searchmatch">mass</span> <span class="searchmatch">of</span> the planet <span class="searchmatch">Earth</span>
Thought: The observation didn't directly give me the mass of Earth, I need to look up the mass of Earth on Wikipedia again
Action: wikipedia: mass of earth in kg
PAUSE
[('wikipedia', 'mass of earth in kg')]
Observation: estimate for the <span class="searchmatch">mass</span> <span class="searchmatch">of</span> <span class="searchmatch">Earth</span> is M🜨 = 5.9722×1024 <span class="searchmatch">kg</span>, with a relative uncertainty <span class="searchmatch">of</span> 10−4. 
It is equivalent to an average density <span class="searchmatch">of</span> 5515 <span class="searchmatch">kg</span>/m3. Using the
Thought: I have the mass of Earth, now I need to multiply it by 10 and take the square root
Action: calculate: (5.9722e24 * 10)**0.5
PAUSE
[('calculate', '(5.9722e24 * 10)**0.5')]
Observation: 7728001035196.618
Thought: I think I have found the answer
Action:
Answer: The square root of the mass of the earth multiplied by 10 is 7728001035196.618.
```
