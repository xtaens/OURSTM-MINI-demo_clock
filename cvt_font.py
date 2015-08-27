#! /usr/bin/python
# -*- coding: utf-8 -*-

from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os, re

TEMPLATE_H = dict(head = '''\
#include <stdint.h>
#define fstr ""\n
#define FONT_GETSIZE(w,h) (w*h>>1)\n
'''
, font = '''\
extern const uint8_t %s[];
'''
, string = '''\
/*%s*/
extern const uint16_t %s[];
'''
, index = '''\
extern const uint16_t %s[];
'''
)

TEMPLATE_C = dict(head = "#include <stdint.h>\n"
, font = '''\
const uint8_t %s[] = {%s};
'''
, string = '''\
/*%s*/
const uint16_t %s[] = {%s};
'''
, index = '''\
const uint16_t %s[] = {%s};
'''
)


#FONT = os.environ['HOME'] + "/.fonts/Android/DroidSansFallback.ttf"
FONT = "/usr/share/fonts/truetype/DroidSansFallbackFull.ttf"
KEYWORD = "_FSTR_"
VAR = "res_string_%s"
VAR_FONT = "res_glyphs"
VAR_INDEX = "res_glyph_index"
PATTERN = re.compile("([\w_]+)/\*%s(.+)\*/" % KEYWORD)
PADDING = -3


charset = u""
strlist = []

def scan(root, suf, exclude):
	for root, dirs, files in os.walk(root):
		for f in files:
			if type(suf) is not list: suf = [suf]
			flag = False
			for s in suf:
				if f.endswith(s) and not f.endswith(exclude+s):
					flag = True
			if flag:
				process(f)
				
def process(fn):
	matches = []
	def process_match(m):
		global charset, strlist
		matches.append(1)
		var, string = m.groups()
		if string in strlist:
			idx = strlist.index(string)
		else:
			idx = len(strlist)
			strlist.append(string)
		for s in string:
			if s not in charset:
				charset+=s	
		return (VAR + "/*" + KEYWORD + "%s*/") % (idx, string)
		
	f = open(fn)
	s = f.read()
	s1 = PATTERN.sub(process_match, s.decode('utf-8'))
	f.close()
	if matches:
		if s1 == s.decode('utf-8'):
			print("%s:unchanged" % fn)
		else:
			print("%s:modified" % fn)
			f = open(fn, 'w')
			f.write(s1.encode('utf-8'))
			f.close()	
		
def render(charset, fontsize, datalist=[]):
	if os.path.isfile(FONT):
		font = ImageFont.truetype(FONT, fontsize)
	else:
		font = ImageFont.load_default()
	
	for char in charset:
		canvas = Image.new('L', (fontsize, fontsize))
		painter = ImageDraw.Draw(canvas)
		size = painter.textsize(char, font = font)
		width = size[0]
		if width > fontsize:
			padding_w = (fontsize + 1 - size[0])/2
			print("FAT CHAR!")
			width = fontsize
		else:
			padding_w = 0
		padding_h = fontsize - size[1]
		padding_h = PADDING
		print("size %s\t:%s\t:%s" % (char.encode('utf-8'), width, padding_h))
		painter.text((padding_w, padding_h), char, font=font, fill = (255))	
		#canvas.show()
		datalist.append(np.array(canvas, dtype = np.uint8)[:,:width] >> 4)
	return datalist
	
def compress(data):
	fontsize, width = data.shape
	assert(data.size & 1 == 0)
	meta = []
	meta.append(fontsize)
	meta.append(width)
	
	res = np.zeros(data.size/2 + len(meta)+1, dtype = np.uint8)
	res[0] = len(meta) + 1 # skip
	res[1:len(meta) + 1] = meta
	i = res[0]
	cnt = 0
	for d in data.reshape(-1):
		if cnt & 1:
			res[i] |= (d << 4) & 0xf0
			i+=1
		else:
			res[i] = d & 0x0f
		cnt +=1
	return res
	
def dump2code(strlist, datalist, fn, mode = None, comment = None):
	if mode is None: mode = 'w'
	fh = open(fn+'.h', mode)
	fc = open(fn+'.c', mode)
	if mode =='w': 
		fh.write(TEMPLATE_H["head"])
		fc.write(TEMPLATE_C["head"])
		
	for i, var in enumerate(strlist):
		var_dec = var.encode('utf-8')
		if comment is None: comment = "%(var_dec)s"
		fh.write(TEMPLATE_H["string"] % (comment % locals(), VAR % i))
		fc.write(TEMPLATE_C["string"] % (comment % locals(), VAR % i,
			', '.join([str(charset.index(c)+1) for c in var]) + ", 0")
			) # 0 for end of string
		
	s = ""
	glyph_index = {}
	offset = 0
	for data in datalist:
		font_size, width = data[1], data[2]
		if font_size not in glyph_index: glyph_index[font_size] = []
		glyph_index[font_size].append(offset)
		offset += data[0] + int(font_size)*int(width)/2
		for i, d in enumerate(data):
			if i % 10 == 0: s+='\n\t'
			s+= hex(d) + ",\t"
		s += '\n\t'
		
	g = "0"
	for key in glyph_index:
		data = glyph_index[key]
		g += ",\t%s,\t%s" % (len(data) + 2, key)
		for i, d in enumerate(data):
			if i % 10 == 0: g+='\n\t'
			g += ",\t" + hex(int(d))
		g += '\n\t'
	g += ", 0"
			
	fh.write(TEMPLATE_H["index"] % (VAR_INDEX))
	fc.write(TEMPLATE_C["index"] % (VAR_INDEX, g))
			
	fh.write(TEMPLATE_H["font"] % (VAR_FONT))
	fc.write(TEMPLATE_C["font"] % (VAR_FONT, s[:-4]))
	
	fh.close()
	fc.close()
	

SRC = "res"

scan("./", [".c", ".h"], SRC)
#process('main.c')

print(charset.encode('utf-8'))
for s in strlist: print(s.encode('utf-8'))	

if charset:
	data0 = []
	data0 = render(charset, 14, data0)
	data0 = render(charset, 48, data0)
	data1 = []
	for d in data0:
		data1.append(compress(d))
	
	dump2code(strlist, data1, SRC)
	
