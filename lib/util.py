__author__ = 'jph'

from Queue import Queue
import threading
import datetime as dt


class QueuePreprocessor(object):
    """
    Adds logging and start/stop functionality to Queue
    """

    def __init__(self, input_queue, enable_logging=True, logfile="log.txt", mode="quiet"):
        """
        Parameters:
        input_queue
        logfile
        mode - (verbose/quiet)
        """
        self.input_queue = input_queue
        self.logfile = logfile
        self.logging_queue = Queue()
        self.enable_logging = enable_logging
        self.mode = mode
        self.output_queue = Queue()
        self.stopped = False
        self.t = threading.Thread(target=self.preprocessing, name="preprocessing_queue",
                                  args=(self.input_queue, self.output_queue, self.logging_queue))
        self.t.daemon = True
        self.t.start()
        self.t2 = threading.Thread(target=self.logging, name="logging_queue",
                                   args=(self.logging_queue, self.logfile, self.mode, self.logging))
        self.t2.daemon = True
        self.t2.start()

    def preprocessing(self, input_queue, output_queue, logging_queue):
        """"
        Takes input queue and output queue, logs every item and stop for start/stop items
        """
        while True:
            element = input_queue.get()
            if element.type == "STOP":
                logging_queue.put(element)
                self.stopped = True
                zwisafe = []
                while self.stopped:
                    element2 = input_queue.get()
                    if element2.type == "STOP":
                        logging_queue.put(element2)
                        for zwielement in zwisafe:
                            logging_queue.put(zwielement)
                            output_queue.put(zwielement)
                        self.stopped = False
                    else:
                        zwisafe.append(element2)
                        #time.sleep(0.001)
            else:
                logging_queue.put(element)
                output_queue.put(element)
                #time.sleep(0.001)

    def logging(self, input_queue, logfile, mode, logging):
        """
        logs and/or outputs all events
        """
        while True:
            element = input_queue.get()
            now = dt.datetime.today()
            if mode == "verbose":
                print element.timestamp
                print element.type
            if logging:
                with open(logfile, 'a') as x:
                    x.write(now.strftime('%m/%d-%H:%M:%S') + "," + element.type + "," + str(element))
                    #time.sleep(0.001)
