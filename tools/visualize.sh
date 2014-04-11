#!/bin/sh

# unflatten visualize.dot > visualize2.dot
# ccomps -Cx visualize.dot | unflatten -l7 | dot | gvpack -array_1 | neato -n2 -Tpng > visualize.png

# this breaks things up into unconnected graphs but it doesn't seem useful
# from http://graphviz.996277.n3.nabble.com/cluster-layout-td3603.html
# ccomps -x visualize.dot | dot | gvpack | neato -s -n2 -Tpng > visualize.png

python visualizer.py $1 > visualize.dot
dot -Tpng visualize.dot -o visualize.png
display visualize.png
