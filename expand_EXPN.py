from math import log
from collections import defaultdict
import re
import pickle

from nltk.corpus import wordnet as wn
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize as wt
from nltk import FreqDist as fd
from nltk import pos_tag

from abbrev_dict import states
from splitter import split
from tag1 import is_digbased
from measurements import meas_dict, meas_dict_pl

with open('word_tokenized_lowered.pickle', mode='rb') as file:
    word_tokenized_lowered = pickle.load(file)

with open('pos_dicts.pickle', mode='rb') as file:
    pos_tag_dict, pos_tag_dict_univ = pickle.load(file)

with open('abbrev_dict.pickle', mode='rb') as file:
    abbrevs = pickle.load(file)

brown = word_tokenized_lowered[:1161192]
brown_common = {word: log(1161192 / freq) for
                word, freq in fd(brown).most_common(5000)[100:]}
words = [w for w, freq in fd(brown).most_common()]


def expand_EXPN(nsw, i, text):
    if nsw in meas_dict and is_digbased(text[i - 1]):
        if text[i - 1] == '1':
            return meas_dict[nsw]
        else:
            return meas_dict_pl[nsw]
    elif (nsw.endswith('.') and nsw[:-1] in meas_dict
          and is_digbased(text[i - 1])):
        if text[i - 1] == '1':
            return meas_dict[nsw[:-1]]
        else:
            return meas_dict_pl[nsw[:-1]]
    if nsw.endswith('.') and nsw[:-1].lower() in abbrevs:
        w = nsw[:-1]
    else:
        w = nsw
    if w.lower() in abbrevs:
        cands = abbrevs[w.lower()]
        true_tag = abbrev_tag(i, text)
        matches = []
        for cand in cands:
            if true_tag in pos_tag_dict[cand.lower()]:
                matches += [cand]
        if not matches:
            true_tag_univ = abbrev_tag_univ(i, text)
            for cand in cands:
                if true_tag_univ in pos_tag_dict_univ[cand.lower()]:
                    matches += [cand]
        if matches:
            best = 0
            current = []
            if len(matches) == 1:
                return matches[0]
            for cand in matches:
                olap = overlap(i, cand, text)
                if olap > best and cand in brown_common:
                    best = olap
                    current = [cand]
                elif olap == best and best != 0:
                    current.append(cand)
                elif cand in states.values() and not current:
                    current.append(cand)
            best = 0
            exp = ''
            for c in current:
                if c in states.values():
                    return c
                elif c in brown_common:
                    freq = brown_common[c]
                else:
                    freq = 0
                if freq > best:
                    best = freq
                    exp = c
        else:
            exp = maximum_overlap(w, i, text)
    else:
        exp = maximum_overlap(w, i, text)
    if exp == '':
        return w
    else:
        return exp


def maximum_overlap(w, i, text):
    best = 0
    current = []
    curr = ''
    if tag_matches(i, text):
        for cand in tag_matches(i, text):
            olap = overlap(i, cand, text)
            if olap > best and cand in words:
                best = olap
                current = [cand]
            elif olap == best and best != 0:
                current.append(cand)
        best = 0
        for c in current:
            if c in brown_common:
                freq = brown_common[c]
            else:
                freq = 0
            if freq > best:
                best = freq
                curr = c
            elif freq == best and len(tag_matches(i, text)) == 1:
                best = freq
                curr = c
            return curr
    if curr == '':
        return w
    else:
        return curr


def overlap(i, word, text):
    overlap = 0
    sig = gen_signature(word)
    context = gen_context(i, text)
    for w in context:
        if w in sig:
            if w in brown_common:
                overlap += brown_common[w]
            else:
                overlap += log(1161192 / 1)
    return overlap


def find_matches(word):
    lst1 = []
    for i in range(len(brown)):
        if brown[i] == word:
            lst1.append(i)
    return lst1


def gen_signature(word):
    inds = find_matches(word)
    signature = defaultdict(int)
    for i in inds:
        for w in gen_context(i, brown):
            signature[w] += 1
    sig = {w for w in signature
           if signature[w] > 1
           and w not in stopwords.words('english') and w != ','}
    if word in wn.words():
        if wn.synsets(word) and "'" not in str(wn.synsets(word)[0]):
            define = (eval("wn.{}.definition()".format(
                      str(wn.synsets(word)[0]).lower())))
            examples = (eval("wn.{}.examples()".format(
                        str(wn.synsets(word)[0]).lower())))
            if examples:
                for ex in examples:
                        sig.update(wt(ex))
            if define:
                        sig.update(wt(define))
    return sig


def gen_context(i, text):
    ind = i
    context = []
    text = text[:]
    if not isinstance(i, int):
        ind = int(i)
        split_token = text[ind]
        del text[ind]
        parts = split({ind: (split_token, 'SPLT')})
        for it in sorted(parts, reverse=True):
            text.insert(ind, parts[it][0])
    start = ind
    end = ind + 1
    sloop = True
    while sloop and start > 0:
        if text[start - 1] not in ['.', '!', '?']:
            start -= 1
        else:
            sloop = False
    eloop = True
    while eloop and end <= len(text) - 1:
        if text[end] in ['.', '!', '?']:
            eloop = False
        else:
            end += 1
    if ind - start < 4:
        if end - start >= 9:
            context += text[start: start + 9]
        else:
            context += text[start: end]
    elif end - ind < 5:
        if end - start >= 9:
            context += text[end - 9: end]
        else:
            context += text[start: end]
    else:
        context += text[ind - 4: ind + 5]
    return context


def tag_sent(i, text):
    sent = gen_context(i, text)
    return pos_tag(sent)


def tag_cands(abbrv):
    tagged_cands = []
    for (cand, freq) in gen_best(abbrv):
        tagged_cands += pos_tag(wt(cand))
    return tagged_cands


def abbrev_tag(i, text):
    for (cand, tag) in tag_sent(i, text):
        if isinstance(i, int):
            if text[i] == cand:
                return tag
        else:
            if split({int(i): (text[int(i)], 'SPLT')})[i][0] == cand:
                return tag


def tag_sent_univ(i, text):
    sent = gen_context(i, text)
    return pos_tag(sent, tagset='universal')


def abbrev_tag_univ(i, text):
    for (cand, tag) in tag_sent_univ(i, text):
        if isinstance(i, int):
            if text[i] == cand:
                return tag
        else:
            if split({int(i): (text[int(i)], 'SPLT')})[i][0] == cand:
                return tag


def tag_matches(i, text):
    matches = []
    if isinstance(i, int):
        abbrev = text[i]
    else:
        abbrev = split({int(i): (text[int(i)], 'SPLT')})[i][0]
    true_tag = abbrev_tag(i, text)
    for (cand, tag) in tag_cands(abbrev):
        if tag == true_tag:
            matches += [cand]
    return matches


def gen_candidates(word):
    cands = []
    reg = ''
    for lt in word.lower():
        if lt.isalpha():
            reg += lt
            reg += '[aeiou]*'
    regex = re.compile(reg)
    for w in words:
        if regex.match(w):
            cands.append(w)
    return cands


def distance(abbrv, word):
    extras = [lt for lt in word if abbrv.count(lt) != word.count(lt)]
    count = 0
    for lt in extras:
        if lt not in ['a', 'e', 'i', 'o', 'u']:
            count += 1
        else:
            count += 0.2
    return count


def gen_best(abbrv):
    cands = [(it, distance(abbrv, it)) for it in gen_candidates(abbrv)]
    sorted_cands = sorted(cands, key=lambda cand: cand[1])
    final = []
    if len(sorted_cands) > 50:
        return sorted_cands[:50]
    else:
        return sorted_cands
