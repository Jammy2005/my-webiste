# my-webiste


I am gunna work on making my personal webiste. 

It going to a chatbot that can provide all the details that the ususal personal website provides.

For the chatbot, I am going to use Langgraph. Tentatively I am thinking that everything shall be in the prompt. I cant imagine that I have so much to say that it require some sort or RAG pipeline.

With start of with prompt, then will evaluate.

I also want some tool calling capacity. Will work on that once the simple chatbot is done. 


#TODO

1. fix the problem with aggregation queries (i.e which projects use langgraph? if not enough chunks retrieved it could fail)

2. fix the vector dB being used, rn i am using chromaDb in memeory not saving to disk, super bad, figure out what works better in prod
