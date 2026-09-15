# Brightway Basic Explorer

Implement a basic activity explorer mostly to use in interractive python such as notebooks, ipython and spyder.

# Install

```
pip install brightway_basic_explorer
```

# Documentation

![Sample Window](https://github.com/gschwind/brightway-basic-explorer/raw/main/doc/sample-window.png)

## Show an activity

```python
import bw2data
from brightway_basic_explorer import show_activity, close_all, search

db = bw2data.Database("ecoinvent-3.11-cutoff")

act = db.search("570kWp")

# Show the first activity
show_activity(act[0])
```

## Close all activities windows

```python
close_all()
```

## With lca_algebraic

If you are ussing lca_algebraic, you can specify parameters. Parameters are completed by default values and used in formula to compute the corresponding amount.

```python
show_activity(act[0], {"paramter0": 10, "parameter1": 20})
```

## Search within a database:

You can search within a database. Search require at less a not too short keyword. Keyword are separated by spaces, for instance:

```python
search("ecoinvent-3.11-cutoff", "570kwp GLO")
```

