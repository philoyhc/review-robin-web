# Assumptions underlying the app

## Hierarchy of structures

# Session
Contains the same universe of Reviewers, Reviewees, Assignments, 1-6 Instruments and their associated Response Forms, Email, deadline
At any one time, operating under one assignment mode (FullMatrix, Manual, RuleBased; note that FullMatrix should be absorbed as a particular rule set)
Status: Draft, Ready (when populated sufficiently, within deadline), Expired (when deadline has passed), Archived (data collected has been downloaded and deleted)
Session can be edited when instruments are closed/paused; if there are ongoing reviews, reviewers need to be notified
Note: While Session is the top level structure, there should be a way to put arbitrarily assign them to Groups. Sessions can be duplicated (without the response data).

# Instrument
Associated with one set of response questions (ratings, comments, etc.) and their instructions
Status: Draft, Receiving responses, Closed/Paused
Closed/Paused defaults to keeping existing responses invisible to reviewers, but visibility can be turned on
Instrument can be edited when closed/paused; if there are ongoing reviews, reviewers need to be notified
Instrument automatically closes upon session deadline

