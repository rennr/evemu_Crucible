/*
    ------------------------------------------------------------------------------------
    LICENSE:
    ------------------------------------------------------------------------------------
    This file is part of EVEmu: EVE Online Server Emulator
    Copyright 2006 - 2021 The EVEmu Team
    For the latest information visit https://evemu.dev
    ------------------------------------------------------------------------------------
    This program is free software; you can redistribute it and/or modify it under
    the terms of the GNU Lesser General Public License as published by the Free Software
    Foundation; either version 2 of the License, or (at your option) any later
    version.

    This program is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
    FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License along with
    this program; if not, write to the Free Software Foundation, Inc., 59 Temple
    Place - Suite 330, Boston, MA 02111-1307, USA, or go to
    http://www.gnu.org/copyleft/lesser.txt.
    ------------------------------------------------------------------------------------
*/

#include "eve-test.h"

#include <cstdio>

namespace {
    int failures = 0;

    void Check(bool ok, const char* what)
    {
        ::printf("%s %s\n", (ok ? "  ok  " : "  FAIL"), what);
        if (!ok)
            ++failures;
    }
}

int utils_DbBoolTest( int /*argc*/, char* /*argv*/[] )
{
    using Parse = bool (*)(const char*);
    Parse parse = &DBResultRow::ParseBool;

    ::printf("DBResultRow::ParseBool:\n");
    Check(!parse(nullptr), "NULL is false");
    Check(!parse(""), "the empty string (a bit(1) holding 0) is false");
    Check(!parse("0"), "tinyint(1) \"0\" is false (its first byte was read as true)");
    Check(parse("1"), "tinyint(1) \"1\" is true");
    Check(parse("\x01"), "bit(1) raw 0x01 is true (text parsing read it as false)");
    Check(!parse("00"), "\"00\" is false");
    Check(parse("-1"), "a negative number is true");
    Check(parse("0x1"), "hex text is parsed");

    if (failures)
        ::printf("%d check(s) failed\n", failures);
    return failures ? 1 : 0;
}
