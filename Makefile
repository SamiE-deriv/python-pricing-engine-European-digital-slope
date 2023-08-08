test:
	dzil test && dzil xtest

pod_test:
	prove -lv t/*pod*.t
