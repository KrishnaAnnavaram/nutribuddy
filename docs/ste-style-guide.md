# The writing standard of nutribuddy: ASD-STE100 Simplified Technical English

Use these rules for the `README.md` of nutribuddy and for this file. Section 3 gives the project
vocabulary. Each term in Section 3 has one meaning in all of the documentation.

## 1. The writing rules

### Words

1. Use one word for one meaning, and one meaning for one word. Do not use synonyms for variety.
2. Use a word only as one part of speech. For example, "test" is a noun or a verb, "check" is a verb.
3. Do not use phrasal verbs (`set up`, `carry out`, `find out`, `pick up`, `look up`, `come up with`).
   Use one verb: "prepare", "do", "find", "get", "make".
4. Do not use an "-ing" form as a noun or an adjective ("the running job", "after indexing").
   Exception: a technical name, a file name, a command or a status value.
5. Do not use contractions (`don't`, `it's`, `can't`). Do not use slang or idioms
   (`out of the box`, `under the hood`, `at a glance`, "gotcha", "bells and whistles").
6. Do not use `and/or`. Write "A, B or both".
7. Do not use `should`, `could`, `would` or `may` for instructions. Use "must" for a rule, the
   imperative for a step and "can" for a possibility.
8. Keep the articles "a", "an" and "the" in sentences.
9. Do not make a noun cluster of more than three words. A technical name is one word.

### Sentences

1. A procedural sentence (an instruction) has a maximum of **20 words**.
2. A descriptive sentence has a maximum of **25 words**.
3. Write one instruction in one sentence.
4. Use the imperative for an instruction: "Run the tests." Not `The tests should be run.`
5. Use the active voice. Use the passive voice only when the agent of the action is not important.
6. Use only the simple present, the simple past and the simple future.
7. Put a condition before the instruction: "If the index is stale, build it again."
8. Do not use semicolons in sentences. Write two sentences.

### Paragraphs, notes and warnings

1. A paragraph has one topic and a maximum of **6 sentences**. Start with the topic sentence.
2. A warning or a caution starts with a clear command. Then it gives the reason.
3. A note gives information. It does not give an instruction.
4. Use a vertical list for a sequence or a set of conditions. Each item of a numbered procedure is one step.

### Tables, headings and diagrams

1. A table cell can be a short phrase. If a cell has a sentence, the sentence obeys the rules.
2. A heading is a noun phrase ("The cost model") or an imperative ("Run the demo").
   Do not start a heading with an "-ing" form.
3. A diagram label is a short phrase. Use the same terms as the text.

### What STE does not change

Code, commands, file names, paths, field names, environment variables, status values, enum values,
product names and URLs stay exactly as they are. They are technical names. Put them in backticks.

## 2. General words to replace

| Do not use | Use |
|---|---|
| utilize, leverage | use |
| in order to | to |
| set up | prepare, install, configure |
| carry out, perform | do |
| make sure, ensure | make sure (allowed), or "check that" |
| a lot of, lots of | many, much |
| e.g., i.e. | for example, that is |
| should (instruction) | must (rule) / imperative (step) |
| might, may (possibility) | can |
| very, really, just, simply, easily | (delete) |
| seamless, robust, powerful, blazing | (delete or give a measured fact) |

## 3. Project vocabulary

These terms have one meaning in the nutribuddy documentation. The code names are in backticks.

### 3.1 Technical names (nouns)

| Term | Meaning | Do not use |
|---|---|---|
| **user** | The person who types symptoms, selects a condition or asks a question. | patient, customer, client |
| **condition** | One of the three supported chronic conditions: `diabetes`, `heart` or `thyroid`. | disease (in prose), illness, disorder (alone) |
| **source** | One registered document with its `id`, title, URL, licence, condition and kind. | paper, file (for a source), reference |
| **registry** | The file `sources.json` that lists all sources. | catalog, manifest (for sources) |
| **kind** | The type of a source: `disease` (symptoms) or `diet_plan` (nutrition guidance). | category, collection |
| **page** | One page of a source. A form feed character separates pages in a text file. | sheet |
| **section** | The text under one Markdown heading inside a page. | part, block |
| **chunk** | One unit of text that nutribuddy stores and retrieves. A chunk is part of one section. | segment, piece, node |
| **overlap** | The words at the end of a chunk that the next chunk of the same section starts with. | stride, carry-over |
| **index** | The folder with `chunks.json`, `vectors.npy` and `manifest.json`. | vector store, database, collection |
| **manifest** | The file `manifest.json`. It holds the embedder name and the fingerprint. | metadata file |
| **fingerprint** | A SHA-256 value of the chunk ids, the chunk texts, the index format and the embedder name. | checksum, hash (alone) |
| **embedder** | The provider that changes a text into a vector. | encoder, embedding service |
| **vector** | The list of numbers that the embedder gives for one text. Each vector has a length of 1. | embedding (as a noun) |
| **hit** | A chunk that the search returns, with its dense score, its lexical score and its fused score. | result, match |
| **passage** | A hit that nutribuddy puts in a prompt with a number `[n]`. | context, snippet, excerpt |
| **marker** | A passage number in square brackets in model text, for example `[2]`. | footnote, tag |
| **citation** | The title, page, section and URL of the source of a valid marker. | reference |
| **evidence check** | The rule that a chunk is a candidate only if it shares a token with the query and its cosine similarity is at least `NUTRIBUDDY_MIN_SCORE`. | answerability check, guard |
| **reranker** | The second search stage that orders the fused candidates again: `coverage`, `cross-encoder` or `none`. | re-scorer |
| **chat model** | The provider that writes the JSON reply or the answer: offline or `openai`. | LLM (in prose), bot, generator |
| **offline model** | The deterministic, extractive chat model. It needs no key and no network. | fake, mock, stub (in prose) |
| **reply** | The raw text that the chat model returns. | response, output |
| **screening** | The step that tells which condition the sources connect to the symptoms. It is not a diagnosis. | diagnosis, prediction, detection |
| **red flag** | A symptom phrase that needs urgent care, for example chest pain. | emergency keyword, alarm |
| **diet plan** | The cited summary, the nutrients, the food examples and the foods to avoid for one condition. | recommendation, advice (as a noun for the output) |
| **food store** | The SQLite database with the tables `nutrient`, `food` and `food_nutrient`. | food DB, nutrition database |
| **food example** | One food from the food store with its amount of one nutrient per 100 g. | suggestion, item |
| **session** | One conversation. The server keeps it in the session store, under a random session id. | chat, cookie |
| **turn** | One user question or one assistant answer in a session. | message (in prose), exchange |
| **refusal** | The reply `{"error": ...}`. The chat model gives it when the passages have no diet advice. | rejection |

### 3.2 Technical verbs

| Verb | Meaning |
|---|---|
| **register** | Add a source to `sources.json`. |
| **chunk** | Split a section into chunks with overlap. |
| **index** | Embed all chunks and write the index folder. |
| **retrieve** | Get hits from the index for a query. |
| **screen** | Do the screening step for a symptom text. |
| **resolve** | Map a nutrient name from a reply to one row of the `nutrient` table. |
| **load** | Upsert the FoodData Central CSV files into the food store. |
| **validate** | Check a reply against its pydantic schema. |
| **escape** | Change `<`, `>`, `&` and quotes into HTML entities before a page shows a text. |
