! C03: WHERE block (masked assign)
program where_block
    implicit none
    integer, dimension(5) :: A, B
    A = [1, -2, 3, -4, 5]
    
    ! The construct below will be traced
    WHERE (A < 0)
        B = -A
    ELSEWHERE
        B = A
    END WHERE
end program where_block
