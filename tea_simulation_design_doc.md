# **TE Simulation Environment Design Doc**

## **Principles**

### **1 Modularity & Reuse:**

There isn't just one "simulation" that will be run. There will be many different types of analyses for different purposes.

Make sure models are decomposed into functional elements with clear, logical input/outputs.

### **2 Explicit Data Models:**

* Data model representations called out *early*  
* Definitions are explicit and done outside of functional code  
* Start *minimal:* what must be modeled today.  
  * Gaps: just more work to handle gracefully.  
* Add information when you need to

### **3 Progressive Automation:**

Don't try to automate a bad system. Build a smooth system where outputs are clearly good or bad.

Then start automating the high-time-spent and low-value-add activities.

### **4 Rapid prototyping & be functional quickly**

This should not be a year-long project before seeing gains.

Requirements:

* Each task can be completed within 4-6 weeks  
* Each tasks adds meaningful as soon as it is complete

### **5 Layer on complexity incrementally**

Once the interfaces are clear and overall flows are function, each individual piece can grow in sophistication independently

# **Design Patterns**

## **Functional Modules**

* Compose simulations and analyses with *functional modules*. Pure inputs \-\> outputs.  
* Modules should be small, logical pieces. Split between domains and ownerships.  
* Inputs and Outputs should be strictly typed data models  
  * Inputs must be strictly validated  
  * Use units everywhere  
  * Data models should be version controlled.  
* The modules will follow the following pattern  
  * Contained in a `class` object  
  * Will have two exposed methods:  
  * `validate_and_fill_default(<inputs>) -> <inputs>`  
    * Validates all inputs to the `run` method  
    * Allows for optional parameters. Make choice of those parameters explicit and traceable  
    * Returns the validated and fully defined inputs  
  * `run(<inputs>) -> <outputs`

## **High-Level Orchestration**

* High-level orchestration is dependent on the type of analysis and simulation that needs to be done. Will include things like:  
  * Retrieving and prepping input data  
  * Executing a dispatch sim  
  * Running post-processing (e.g. economic analysis)  
* "High-Level Orchestration" is characterized by discrete modules that can be run asynchronously  
* Two modes of usage:  
  * Manual, notebook-based calls. Good when individual modules may actually be manual or customized.  
  * Pipeline driven. Define a DAG-like pipeline of components strung together (think a "yaml"-like config). Use for automated runs.  
    * Bookended by "Entry Point" (validates all input data is there to satisfy DAG) and "Exit Point" (composes all data collected for returning)  
* Meta analysis, like sweeps and optimizations:  
  * The single-sim pipeline is now a module, whose input/output is defined by Entry Point and Exit Point  
  * The Entry Point and Exit point will be defined like functional models, but defined dynamically based on the sim configuration  
* Choice of components and orchestration will be done in a YAML-like configuration

## **Dynamical Simulation**

* Characterized by multiple models run synchronously; hence, use of time-based simulation solver  
* These models will be exposed as "SynchronousComponents"  
* These are wrapped by an asynchronous module \`SynchronousSim\`  
  * See below simplified code (in reality, deal with `ndarray` slicing, ensure coherency)

