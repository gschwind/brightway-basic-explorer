# Brightway Basic Explorer

Implement a basic activity explorer mostly to use in interractive python such as notebooks, ipython and spyder.

# Install

```
pip install brightway_basic_explorer
```

# Sample and Documentation

![Sample Window](https://github.com/gschwind/brightway-basic-explorer/raw/main/doc/sample-window.png)

```python
import bw2data
from brightway_basic_explorer import show_activity, close_all

db = bw2data.Database("ecoinvent-3.11-cutoff")

act = db.search("570kWp")

# Show the first activity
show_activity(act[0])

# Close all activity windows
close_all()
```
