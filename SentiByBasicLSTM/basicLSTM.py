#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2017/9/12 10:03
# @Author  : Su.

import pandas as pd
import numpy as np
import jieba
import yaml
from gensim.corpora.dictionary import Dictionary
from keras.preprocessing import sequence
import multiprocessing
from gensim.models.word2vec import Word2Vec
from keras.models import Sequential
from keras.layers.embeddings import Embedding
from keras.layers.recurrent import LSTM
from keras.layers.core import Dense, Dropout,Activation
from keras.models import model_from_yaml
from sklearn.model_selection import train_test_split


import yaml
import sys
reload(sys)
sys.setdefaultencoding('utf8')
from sklearn.model_selection import train_test_split
import multiprocessing
import numpy as np
from gensim.models.word2vec import Word2Vec
from gensim.corpora.dictionary import Dictionary

from keras.preprocessing import sequence
from keras.models import Sequential
from keras.layers.embeddings import Embedding
from keras.layers.recurrent import LSTM
from keras.layers.core import Dense, Dropout,Activation
from keras.models import model_from_yaml
np.random.seed(1337)  # For Reproducibility
import jieba
import pandas as pd
sys.setrecursionlimit(1000000)
import os
from utils import result

# set parameters:
vocab_dim = 100
maxlen = 100
n_iterations = 5  # ideally more..
n_exposures = 10
window_size = 7
batch_size = 32
n_epoch = 10
input_length = 100
cpu_count = multiprocessing.cpu_count()



rootPath = "/mnt/hgfs/data/senitment_data"
trainPath = os.path.join(rootPath, "train.csv")
testPath = os.path.join(rootPath, "test.csv")

word2veModelPath = os.path.join(rootPath,"basic_lstm/word2vecmodel.pkl")
h5_path =  os.path.join(rootPath,"basic_lstm/lstm.h5")
yml_path =  os.path.join(rootPath,"basic_lstm/lstm.yml")

#加载训练文件
def loadfile():
    data = pd.read_csv(trainPath, sep="\t")
    trainX = data["text"]
    trainY = []
    for score in list(data["score"]):
        if score == 0:
            trainY.append([1, 0, 0])
        elif score == 1:
            trainY.append([0, 1, 0])
        else:
            trainY.append([0, 0, 1])
    return trainX, np.array(trainY)

#对句子经行分词，并去掉换行符
def tokenizer(text):
    ''' Simple Parser converting each document to lower-case, then
        removing the breaks for new lines and finally splitting on the
        whitespace
    '''
    text = [jieba.lcut(str(document).replace('\n', '')) for document in text]
    return text



#创建词语字典，并返回每个词语的索引，词向量，以及每个句子所对应的词语索引
def create_dictionaries(model=None,
                        combined=None):
    ''' Function does are number of Jobs:
        1- Creates a word to index mapping
        2- Creates a word to vector mapping
        3- Transforms the Training and Testing Dictionaries

    '''
    if (combined is not None) and (model is not None):
        gensim_dict = Dictionary()
        gensim_dict.doc2bow(model.wv.vocab.keys(),
                            allow_update=True)
        w2indx = {v: k+1 for k, v in gensim_dict.items()}#所有频数超过10的词语的索引
        w2vec = {word: model[word] for word in w2indx.keys()}#所有频数超过10的词语的词向量

        def parse_dataset(combined):
            ''' Words become integers
            '''
            data=[]
            for sentence in combined:
                new_txt = []
                for word in sentence:
                    try:
                        new_txt.append(w2indx[word])
                    except:
                        new_txt.append(0)
                data.append(new_txt)
            return data
        combined=parse_dataset(combined)
        combined= sequence.pad_sequences(combined, maxlen=maxlen)#每个句子所含词语对应的索引，所以句子中含有频数小于10的词语，索引为0
        return w2indx, w2vec,combined
    else:
        print 'No data provided...'


#创建词语字典，并返回每个词语的索引，词向量，以及每个句子所对应的词语索引
def word2vec_train(combined):

    model = Word2Vec(size=vocab_dim,
                     min_count=n_exposures,
                     window=window_size,
                     workers=cpu_count,
                     iter=n_iterations)
    model.build_vocab(combined)
    model.train(combined)
    model.save(word2veModelPath)
    index_dict, word_vectors,combined = create_dictionaries(model=model,combined=combined)
    return   index_dict, word_vectors,combined

def get_data(index_dict,word_vectors,combined,y):

    n_symbols = len(index_dict) + 1  # 所有单词的索引数，频数小于10的词语索引为0，所以加1
    embedding_weights = np.zeros((n_symbols, vocab_dim))#索引为0的词语，词向量全为0
    for word, index in index_dict.items():#从索引为1的词语开始，对每个词语对应其词向量
        embedding_weights[index, :] = word_vectors[word]
    x_train, x_test, y_train, y_test = train_test_split(combined, y, test_size=0.2)
    print x_train.shape,y_train.shape
    return n_symbols,embedding_weights,x_train,y_train,x_test,y_test


##定义网络结构
def train_lstm(n_symbols,embedding_weights,x_train,y_train,x_test,y_test):
    print 'Defining a Simple Keras Model...'
    model = Sequential()  # or Graph or whatever
    model.add(Embedding(output_dim=vocab_dim,
                        input_dim=n_symbols,
                        mask_zero=True,
                        weights=[embedding_weights],
                        input_length=input_length))  # Adding Input Length
    model.add(LSTM(output_dim=50, activation='relu', inner_activation='hard_sigmoid'))
    model.add(Dropout(0.5))
    # model.add(Dense(1))
    # model.add(Activation('sigmoid'))
    model.add(Dense(output_dim=3,input_dim=50, activation='softmax'))

    print 'Compiling the Model...'
    model.compile(loss='categorical_crossentropy',
                  optimizer='adam',metrics=['accuracy'])

    print "Train..."
    model.fit(x_train, y_train, batch_size=batch_size, nb_epoch=n_epoch,verbose=1, validation_data=(x_test, y_test))

    print "Evaluate..."
    score = model.evaluate(x_test, y_test,
                                batch_size=batch_size)

    yaml_string = model.to_yaml()
    with open(yml_path, 'w') as outfile:
        outfile.write( yaml.dump(yaml_string, default_flow_style=True) )
    model.save_weights(h5_path)
    print 'Test score:', score


#训练模型，并保存
def train():
    print 'Loading Data...'
    combined,y=loadfile()
    print len(combined),len(y)
    print 'Tokenising...'
    combined = tokenizer(combined)
    print 'Training a Word2vec model...'
    index_dict, word_vectors,combined=word2vec_train(combined)
    print 'Setting up Arrays for Keras Embedding Layer...'
    n_symbols,embedding_weights,x_train,y_train,x_test,y_test=get_data(index_dict, word_vectors,combined,y)
    print x_train.shape,y_train.shape
    train_lstm(n_symbols,embedding_weights,x_train,y_train,x_test,y_test)




def input_transform(string):
    words=jieba.lcut(string)
    words=np.array(words).reshape(1,-1)
    model=Word2Vec.load(word2veModelPath)
    _,_,combined=create_dictionaries(model,words)
    return combined

def lstm_predict(string):
    print 'loading model......'
    with open(yml_path, 'r') as f:
        yaml_string = yaml.load(f)
    model = model_from_yaml(yaml_string)

    print 'loading weights......'
    model.load_weights(h5_path)
    model.compile(loss='categorical_crossentropy',
                  optimizer='adam',metrics=['accuracy'])
    data=input_transform(string)
    data.reshape(1,-1)
    #print data
    result=model.predict_classes(data)
    # if result[0][0]==1:
    #     print string,' positive'
    # else:
    #     print string,' negative'
    print result


def evaluate():
    print 'loading model......'
    with open(yml_path, 'r') as f:
        yaml_string = yaml.load(f)
    model = model_from_yaml(yaml_string)

    print 'loading weights......'
    model.load_weights(h5_path)
    model.compile(loss='categorical_crossentropy',
                  optimizer='adam',metrics=['accuracy'])


    testData = pd.read_csv(testPath, sep="\t")
    testX = list(testData["text"])
    y_pred = []
    print testX[0]
    for i in xrange(len(testData)):


        data=input_transform(str(testX[i]))
        data.reshape(1,-1)
        pred_value = model.predict_classes(data)
        y_pred.append(pred_value[0])

    save_path = "doc/result.txt"
    desc = "basic lstm"
    result_str = result.printMultiResult(testData["score"], y_pred)
    result.saveResult(save_path,desc, result_str)








if __name__=='__main__':
    #train()
    #string='电池充完了电连手机都打不开.简直烂的要命.真是金玉其外,败絮其中!连5号电池都不如'
    # string='牛逼的手机，从3米高的地方摔下去都没坏，质量非常好'
    # string='酒店的环境非常好，价格也便宜，值得推荐'
    # string='手机质量太差了，傻逼店家，赚黑心钱，以后再也不会买了'
    string='我是傻逼'
    # string='一般般'
    # string='屏幕较差，拍照也很粗糙。'
    # string='质量不错，是正品 ，安装师傅也很好，才要了83元材料费'
    # string='喜欢'
    # train()

    # evaluate_result()

    lstm_predict(string)


