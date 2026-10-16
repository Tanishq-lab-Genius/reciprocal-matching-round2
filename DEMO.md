# Quick Demo

Run this from the project folder:

```sh
python3 demo.py
```

The script uses the submitted `selective_joint_voi` policy with the included public synthetic simulator. It prints one reproducible day showing the observable pool, reciprocal hard-eligibility counts, questions selected by ASK, the refreshed state, and the final MATCH action. It uses seed 15 and a 12-person generated world so the demonstration is short and repeatable.

The simulator resolves questions from its synthetic world, but the policy receives only the public observation and refreshed observation. The example is for demonstrating how the policy works; it is not an official benchmark result or evidence of real-world performance.
