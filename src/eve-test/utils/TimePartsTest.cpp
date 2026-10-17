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
#include <ctime>

#include "utils/utils_time.h"

namespace {
    int failures = 0;

    void Check(bool ok, const char* what)
    {
        ::printf("%s %s\n", (ok ? "  ok  " : "  FAIL"), what);
        if (!ok)
            ++failures;
    }

    // FILETIME for a unix time (seconds) plus 100ns intervals
    int64 FileTime(int64 unixTime, int64 extra = 0)
    {
        return (unixTime + 11644473600LL) * EvE::Time::Second + extra;
    }

    bool Is(const EvE::TimeParts& p, int y, int mo, int d, int h, int mi, int s)
    {
        return (p.year == y) and (p.month == mo) and (p.day == d)
           and (p.hour == h) and (p.min == mi) and (p.sec == s);
    }
}

int utils_TimePartsTest( int /*argc*/, char* /*argv*/[] )
{
    ::printf("GetTimeParts:\n");

    EvE::TimeParts p = GetTimeParts(FileTime(0));
    Check(Is(p, 1970, 1, 1, 0, 0, 0) and (p.wd == 4) and (p.dy == 1) and (p.wn == 1), "the unix epoch, a Thursday");

    p = GetTimeParts(FileTime(1798678800));
    Check(Is(p, 2026, 12, 31, 1, 0, 0) and (p.dy == 365) and (p.wn == 53), "Dec 31 of a common year (the old year loop took a year off here)");

    p = GetTimeParts(FileTime(1861790400));
    Check(Is(p, 2028, 12, 30, 12, 0, 0) and (p.dy == 365) and (p.wd == 6), "Dec 30 of a leap year (the old loop wrapped to 2208)");

    p = GetTimeParts(FileTime(1861919999));
    Check(Is(p, 2028, 12, 31, 23, 59, 59) and (p.dy == 366) and (p.wd == 0), "the last second of a leap year");

    p = GetTimeParts(FileTime(1835460736));
    Check(Is(p, 2028, 2, 29, 18, 12, 16) and (p.dy == 60), "Feb 29, just past 18:12:15 (the old uint16 seconds overflowed)");

    p = GetTimeParts(FileTime(1792267200));
    Check(Is(p, 2026, 10, 17, 20, 0, 0) and (p.wn == 42), "an evening hour");

    p = GetTimeParts(FileTime(951868800, 1234567));
    Check(Is(p, 2000, 3, 1, 0, 0, 0) and (p.ms == 123), "Mar 1 of a 400-year leap year, with milliseconds");

    p = GetTimeParts(0);
    Check(Is(p, 1601, 1, 1, 0, 0, 0), "FILETIME 0 is 1601-01-01, not now");

    p = GetTimeParts(-1);
    Check(Is(p, 1601, 1, 1, 0, 0, 0), "a negative time is clamped, not thrown");

    p = GetTimeParts(INT64_MAX);
    Check(Is(p, 9999, 12, 31, 23, 59, 59), "a huge (client-sent) time is clamped, not thrown");

    std::time_t before = std::time(nullptr);
    p = GetTimeParts();
    std::tm utc = *std::gmtime(&before);
    Check((p.year == utc.tm_year + 1900) and (p.month == utc.tm_mon + 1)
          and ((p.day == utc.tm_mday) or (p.hour == 0)), "no argument is now (UTC)");

    if (failures)
        ::printf("%d check(s) failed\n", failures);
    return failures ? 1 : 0;
}
