"ansisym error funnel"

#   Copyright 2013 David B. Curtis

#   This file is part of ansisym.
#   
#   ansisym is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#   
#   ansisym is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#   
#   You should have received a copy of the GNU General Public License
#   along with ansisym.  If not, see <http://www.gnu.org/licenses/>.
#   

class ansisymPanic(Exception):
    pass

class ErrorSink(object):
    "Funnels error messages, keeps counts by severity."
    _counters = {'i':0,'w':0,'f':0,'p':0}
    _sevSpell = {'i':'INFO','w':'WARNING','f':'FATAL','p':'PANIC'}
    def msg(self, sev, message):
        self._counters[sev] += 1
        print ': '.join([self._sevSpell[sev],message])
        if sev == 'p':
            raise ansisymPanic
    @property
    def counts(self):
        return (self._counters['i'], self._counters['w'], 
                self._counters['f'], self._counters['p'])
    @property
    def haveFatalErrors(self):
        return self._counters['f'] > 0 or self._counters['p'] > 0

# Single instance of ErrorSink class.
# The goofy name becomes readable if this module is imported as 'er',
# for example:
#   import ansisymErrorSink as er
#   er.ror.msg('f','Foo')
ror = ErrorSink()
