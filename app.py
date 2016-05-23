from pyspark import SparkContext
from datetime import datetime
from datetime import timedelta
import os, errno

# To run program: spark-submit app.py

# Creates a tuple where the ip is the key and the related data is put in a list of values
def ip_package(lineTuple):
    if len(lineTuple) < 17:
        return [];

    # Only need the time, website, and ip (without the port number)
    ip = lineTuple[2].split(':')[0];
    sessionData = [lineTuple[0], lineTuple[12]];
    package = [ip, sessionData];

    return package;

# Create session files for each IP address
# package = (ip, [[timeStamp, url], ...])
def sessionize(package):
    try:
        os.makedirs("sessions")
    except OSError:
        if not os.path.isdir("sessions"):
            raise
    try:
        sessionsFP = open("sessions/" + str(package[0]) + ".log", "a");
        sessionsLenFP = open("sessions/sessionLength.log", "a");
        visted = [];
        sessionStart = datetime.min;
        sessionIdleLimit = sessionStart + timedelta(minutes=15);
        timeFormat = "%Y-%m-%dT%H:%M:%S.%fZ";

        # Go through each visited page to sessionize the data
        # hit[0] = timeStamp
        # hit[1] = URL
        for hit in package[1]:
            nextTime = datetime.strptime(hit[0], timeFormat);

            # Start a new session
            if nextTime > sessionIdleLimit:
                if (sessionStart != datetime.min):
                    # Record the length of the old session; leading 0 for formatting
                    sessionTime = sessionIdleLimit - sessionStart;
                    sessionsLenFP.write(str(sessionTime.total_seconds()) + " " + package[0] + "\n");

                # Begin the new session
                sessionStart = datetime.strptime(hit[0], timeFormat);
                sessionIdleLimit = sessionStart + timedelta(minutes=15);
                visited = [];
                visited.append(hit[1]);
                sessionsFP.write("\n--NEW--\n")
                sessionsFP.write(hit[0] + " " + hit[1] + "\n");

            else:
                # Continue session
                if hit[1] not in visited:
                    visited.append(hit[1]);
                    sessionIdleLimit = nextTime + timedelta(minutes=15);
                    sessionsFP.write(hit[0] + " " + hit[1] + "\n");

        if (sessionStart != datetime.min):
            # Record the length of the last session
            sessionTime = sessionIdleLimit - sessionStart;
            sessionsLenFP.write(str(sessionTime.total_seconds()) + " " + package[0] + "\n");

        sessionsFP.close();
        sessionsLenFP.close();
    except IOError:
        print ("Could not write to file.");

if __name__ == "__main__":
    sc = SparkContext('local','example')

    # Group similar ip data together (ip, [[timeStamp, url], ...])
    # Assumes the log file is sorted by time already
    # returns tuple of collected data
    logTuples = sc.textFile("data/sample.log").map(lambda line: ip_package(line.replace('\"', "").split(" "))) \
                                            .map(lambda (x, y): (x, [y])) \
                                            .reduceByKey(lambda a, b : a + b) \
                                            .foreach(sessionize);

    # Parses the line from the sessionLength file
    avg = sc.textFile("sessions/sessionLength.log").map(lambda line: line.split(" ")) \
                                                   .collect();

    # Sum up the session times to find the average
    totalDelta = 0
    for x in avg:
        totalDelta += float(x[0]);
    totalAVG = totalDelta/len(avg);

    try:
        fp = open("sessions/avg.log","w");
        fp.write(str(totalAVG));
        fp.close();
    except IOError:
        print ("Could not write/open file.")

    # Find users with session times longer than average
    try:
        fp = open("sessions/longUsers.log", "a");

        for x in avg:
            if x[0] > totalAVG:
                fp.write(str(x[0]) + " " + str(x[1]));
                fp.write("\n")

        fp.close();

    except IOError:
        print ("Could not write/open file.");
