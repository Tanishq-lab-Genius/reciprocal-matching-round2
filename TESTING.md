# Verification

Run the included verification tests:

```sh
python3 -m unittest -v test_kit test_matching_core test_matching_policy test_directional_learning test_msmi_feedback test_release test_runner
```

Build and run the submitted container:

```sh
docker build -t reciprocal-matching-round2 .
printf '{"schema_version":"1.0.0","phase":"ask","state":{"day":0,"members":[],"introductions":[],"question_budget":0},"memory":null}\n' | docker run --rm -i reciprocal-matching-round2
```

The Dockerfile runs `reciprocal_matching_policy.py`, whose submitted default is `selective_joint_voi`.
