from pypy.rlib.jit import hint, jit_merge_point, can_enter_jit


MOV_A_R    = 1
MOV_R_A    = 2
JUMP_IF_A  = 3
SET_A      = 4
ADD_R_TO_A = 5
RETURN_A   = 6
ALLOCATE   = 7
NEG_A      = 8


def interpret(bytecode, a):
    """Another Toy Language interpreter, this one register-based."""
    regs = []
    pc = 0
    while True:
        hint(None, global_merge_point=True)
        opcode = hint(ord(bytecode[pc]), concrete=True)
        pc += 1
        if opcode == MOV_A_R:
            n = ord(bytecode[pc])
            pc += 1
            regs[n] = a
        elif opcode == MOV_R_A:
            n = ord(bytecode[pc])
            pc += 1
            a = regs[n]
        elif opcode == JUMP_IF_A:
            target = ord(bytecode[pc])
            pc += 1
            if a:
                pc = target
        elif opcode == SET_A:
            a = ord(bytecode[pc])
            pc += 1
        elif opcode == ADD_R_TO_A:
            n = ord(bytecode[pc])
            pc += 1
            a += regs[n]
        elif opcode == RETURN_A:
            return a
        elif opcode == ALLOCATE:
            n = ord(bytecode[pc])
            pc += 1
            regs = [0] * n
        elif opcode == NEG_A:
            a = -a

def hp_interpret(bytecode, a):
    """A copy of interpret() with the hints required by the hotpath policy."""
    regs = []
    pc = 0
    while True:
        jit_merge_point(green=(bytecode, pc), red=(a, regs))
        opcode = hint(ord(bytecode[pc]), concrete=True)
        pc += 1
        if opcode == MOV_A_R:
            n = ord(bytecode[pc])
            pc += 1
            regs[n] = a
        elif opcode == MOV_R_A:
            n = ord(bytecode[pc])
            pc += 1
            a = regs[n]
        elif opcode == JUMP_IF_A:
            target = ord(bytecode[pc])
            pc += 1
            if a:
                if target < pc:
                    can_enter_jit(green=(bytecode, target), red=(a, regs))
                pc = target
        elif opcode == SET_A:
            a = ord(bytecode[pc])
            pc += 1
        elif opcode == ADD_R_TO_A:
            n = ord(bytecode[pc])
            pc += 1
            a += regs[n]
        elif opcode == RETURN_A:
            return a
        elif opcode == ALLOCATE:
            n = ord(bytecode[pc])
            pc += 1
            regs = [0] * n
        elif opcode == NEG_A:
            a = -a

# ____________________________________________________________
# example bytecode: compute the square of 'a' >= 1

SQUARE_LIST = [
    ALLOCATE,    3,
    MOV_A_R,     0,   # counter
    MOV_A_R,     1,   # copy of 'a'
    SET_A,       0,
    MOV_A_R,     2,   # accumulator for the result
    # 10:
    SET_A,       1,
    NEG_A,
    ADD_R_TO_A,  0,
    MOV_A_R,     0,
    MOV_R_A,     2,
    ADD_R_TO_A,  1,
    MOV_A_R,     2,
    MOV_R_A,     0,
    JUMP_IF_A,  10,

    MOV_R_A,     2,
    RETURN_A ]

SQUARE = ''.join([chr(n) for n in SQUARE_LIST])

if __name__ == '__main__':
    print ','.join([str(n) for n in SQUARE_LIST])
