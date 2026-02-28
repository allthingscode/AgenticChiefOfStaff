# LLM Routing Test Suite

This directory contains a set of simple text files designed to test and verify the multi-model LLM routing functionality.

## How to Run the Tests

To run a test, simply send the content of one of the `test_*.txt` files as a prompt to the nanobot agent.

You can do this by copying the text from the file and pasting it into the chat, or by using a command like:

```bash
nanobot send < tests/routing/test_local_model.txt
```

## How to Verify the Results

The key to verification is observing the application logs. The logs will explicitly state which model was chosen by the router for a given prompt.

1.  **Start the nanobot application** in a terminal so you can see the live log output.
2.  **Send the prompt** from one of the test files.
3.  **Check the logs** for a line similar to this:

    ```
    INFO | nanobot.agent.loop:_route_prompt:315 - Routing prompt to model: [model_name]
    ```

    - For `test_local_model.txt`, the log should say `model: 'ollama/llama3.1:8b'`.
    - For `test_fast_model.txt`, the log should say `model: 'gemini-1.5-flash'`.
    - For `test_powerful_model.txt`, the log should say `model: 'gemini-1.5-pro'`.

By confirming the log output matches the expected model for each test case, you can verify that the routing system is working correctly.
