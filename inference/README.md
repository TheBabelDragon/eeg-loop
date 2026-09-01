# Inference

Conceptual API:

```
EEGFrame
   |
SignalQuality
   |
FeatureVector
   |
StateVector
```

```
FeatureVector {
    delta_power
    theta_power
    alpha_power
    beta_power
    gamma_power
    spectral_entropy
    variance
    artifact_probability
}

StateVector {
    features
    baseline_delta
    confidence
    timestamp
}
```

Keep the distinction explicit:

**measurement is not interpretation.**

Do not initially translate features into focus, happiness, consciousness, or relaxation.

The first model is individual, not universal:

```
PERSON
 |
baseline recording
 |
individual feature distribution
 |
relative deviation
```

Example:

```
alpha_power
baseline: 1.00
current:  1.34
relative: +34%
confidence: ...
```

If artifact probability is high, emit `NO VALID INFERENCE` instead of a confident state.
